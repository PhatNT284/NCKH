"""
Test cho src/workflow_state.py — khoi (f) cua san pham D3.

Hoan tat hai bat bien con lai cua giao thuc:
    INV-5  luu ban ghi roi tinh lai -> ra DUNG phan quyet cu
    INV-6  D3 khong chua mo hinh hoc may nao

Nam nhom:
    TestMissionRecord   ban ghi va tinh tu-no-la-du
    TestFreshness       P§4.2 — dau con han
    TestInv5Replay      tinh lai tu ban ghi
    TestOutcome         truong ket cuc ghi doc lap
    TestInv6NoModel     quet ma nguon
"""

from __future__ import annotations

import json

import pytest

from src.workflow_state import (
    FRESH, OUTCOME_ABORTED, OUTCOME_COMPLETED, OUTCOME_NOT_FLOWN,
    OUTCOME_UNKNOWN, SAFETY_INPUTS, STALE, MissionRecord, capture_versions,
    check_freshness, evaluate, record_outcome, recompute, replay,
    replay_matches, scan_for_learned_models,
)

GOC = dict(payload_g=250, speed_commanded_ms=8, altitude_m=50,
           distance_2d_m=472, wind_forecast_ms=3.0, ambient_temp_c=15,
           soc=0.30, soh=0.95, e_required_Wh=22.0)
LUC_8H = "2026-10-15T08:00:00+00:00"


def _rec(**kw) -> MissionRecord:
    return evaluate("M-001", created_at=LUC_8H, **{**GOC, **kw})


# ---------------------------------------------------------------------------

class TestMissionRecord:
    """Ban ghi phai TU NO LA DU — P§4.2, RQ4."""

    def test_ghi_duoc_phan_quyet(self):
        r = _rec()
        assert r.verdict == "FLY"
        assert r.state == FRESH
        assert r.is_fresh

    def test_ghi_du_moi_dau_vao_an_toan(self):
        r = _rec()
        for truong in SAFETY_INPUTS:
            assert truong in r.inputs, f"thieu {truong} trong ban ghi"

    def test_ghi_du_phien_ban(self):
        """Thieu mot muc phien ban la mat kha nang tinh lai."""
        v = _rec().versions
        for khoa in ("protocol_version", "estimator", "reserve_factor",
                     "uncertainty_allowance_Wh", "validity_envelope_m",
                     "e_nominal_Wh", "kappa_range_c"):
            assert khoa in v

    def test_phien_ban_khop_giao_thuc(self):
        from src.decision_rules import load_protocol
        p = load_protocol()
        v = _rec().versions
        assert v["protocol_version"] == p["meta"]["version"]
        assert v["estimator"] == p["energy_required"]["estimator"]

    def test_ghi_du_dai_luong_nang_luong(self):
        r = _rec()
        assert r.e_available_Wh is not None
        assert r.e_required_Wh == 22.0
        assert r.margin_Wh == pytest.approx(r.e_available_Wh - r.e_required_Wh)

    def test_json_khu_hoi_duoc(self):
        r = _rec()
        lai = MissionRecord.from_json(r.to_json())
        assert lai == r

    def test_json_la_van_ban_thuan(self):
        """Phai luu duoc ra file, gui qua mang, doc bang mat."""
        d = json.loads(_rec().to_json())
        assert isinstance(d, dict)
        assert d["verdict"] == "FLY"

    def test_mac_dinh_la_con_han(self):
        assert _rec().state == FRESH


# ---------------------------------------------------------------------------

class TestFreshness:
    """
    P§4.2: "when any safety-relevant input, the mission plan, the aircraft or
    battery selection, a threshold or the model itself changes, the previous
    assessment is marked stale and must be recomputed before the mission may
    proceed."
    """

    @pytest.mark.parametrize("truong,moi", [
        ("wind_forecast_ms", 12.0),
        ("ambient_temp_c", -5.0),
        ("soc", 0.50),
        ("soh", 0.80),
        ("payload_g", 500),
        ("distance_2d_m", 600),
        ("speed_commanded_ms", 12),
        ("battery_type", "TB48D"),
        ("e_required_Wh", 25.0),
    ])
    def test_doi_dau_vao_lam_het_han(self, truong, moi):
        r = check_freshness(_rec(), current_inputs={truong: moi})
        assert r.state == STALE
        assert any(truong in ly for ly in r.stale_reasons)

    def test_khong_doi_gi_thi_van_con_han(self):
        r = _rec()
        assert check_freshness(r, current_inputs=dict(r.inputs)).state == FRESH

    def test_doi_mo_hinh_lam_het_han(self):
        """
        De quen nhat: mo hinh D2 huan luyen lai thi MOI danh gia cu deu het han,
        vi con so "can bao nhieu Wh" da khac.
        """
        v = capture_versions()
        v["estimator"] = "D2_ridge_v2"
        assert check_freshness(_rec(), current_versions=v).state == STALE

    def test_doi_nguong_lam_het_han(self):
        v = capture_versions()
        v["reserve_factor"] = 0.30
        assert check_freshness(_rec(), current_versions=v).state == STALE

    def test_doi_giao_thuc_lam_het_han(self):
        v = capture_versions()
        v["protocol_version"] = "9.9.9"
        assert check_freshness(_rec(), current_versions=v).state == STALE

    def test_doi_envelope_lam_het_han(self):
        v = capture_versions()
        v["validity_envelope_m"] = [300, 900]
        assert check_freshness(_rec(), current_versions=v).state == STALE

    def test_het_han_thi_khong_duoc_tien_hanh(self):
        """
        Diem mau chot. Phan quyet cu VAN LA FLY, nhung khong duoc bay — phai
        tinh lai truoc.
        """
        r = check_freshness(_rec(), current_inputs={"wind_forecast_ms": 12.0})
        assert r.verdict == "FLY"
        assert not r.may_proceed

    def test_con_han_va_fly_thi_duoc_tien_hanh(self):
        assert _rec().may_proceed

    def test_con_han_nhung_no_fly_thi_khong_duoc(self):
        assert not _rec(soc=0.25).may_proceed

    def test_insufficient_data_thi_khong_duoc(self):
        assert not _rec(soc=None).may_proceed

    def test_khong_sua_ban_ghi_goc(self):
        """Ban goc phai tra cuu duoc nguyen ven ve sau."""
        goc = _rec()
        check_freshness(goc, current_inputs={"wind_forecast_ms": 12.0})
        assert goc.state == FRESH
        assert goc.stale_reasons == []

    def test_liet_ke_het_moi_thay_doi(self):
        r = check_freshness(_rec(), current_inputs={
            "wind_forecast_ms": 12.0, "soc": 0.50, "payload_g": 500})
        assert len(r.stale_reasons) >= 3

    def test_truong_la_bi_tu_choi(self):
        """Chan loi go nham ten truong — im lang bo qua thi nguy hiem."""
        with pytest.raises(ValueError, match="khong thuoc dau vao an toan"):
            check_freshness(_rec(), current_inputs={"gio": 12.0})

    def test_tinh_lai_cho_phan_quyet_moi(self):
        r = check_freshness(_rec(), current_inputs={"wind_forecast_ms": 12.0})
        moi = recompute(r, current_inputs={"wind_forecast_ms": 12.0})
        assert moi.verdict == "NO_FLY"
        assert moi.state == FRESH
        assert moi.mission_id == r.mission_id

    def test_tinh_lai_giu_ket_cuc_da_ghi(self):
        r = record_outcome(_rec(), OUTCOME_COMPLETED, "xong")
        moi = recompute(r, current_inputs={"soc": 0.50})
        assert moi.outcome == OUTCOME_COMPLETED
        assert moi.outcome_note == "xong"


# ---------------------------------------------------------------------------

class TestInv5Replay:
    """INV-5 — luu ban ghi roi tinh lai ra DUNG phan quyet cu."""

    @pytest.mark.parametrize("kw", [
        {},                                  # FLY
        {"soc": 0.28},                       # CONDITIONAL
        {"soc": 0.25},                       # NO_FLY
        {"soc": None},                       # INSUFFICIENT_DATA
        {"wind_forecast_ms": 14.0},          # vi pham luat cung
        {"distance_2d_m": 835},              # ngoai suy
    ])
    def test_tinh_lai_khop_moi_nhanh(self, kw):
        r = _rec(**kw)
        assert replay_matches(r), f"tinh lai lech o truong hop {kw}"

    def test_tinh_lai_qua_json(self):
        """Duong di that: luu ra file, doc lai, tinh lai."""
        r = _rec()
        lai = MissionRecord.from_json(r.to_json())
        assert replay_matches(lai)

    def test_tinh_lai_giu_nguyen_ly_do(self):
        r = _rec(soc=0.28)
        assert replay(r).reasons == r.reasons

    def test_tinh_lai_giu_mission_id_va_thoi_gian(self):
        r = _rec()
        lai = replay(r)
        assert lai.mission_id == r.mission_id
        assert lai.created_at == r.created_at

    def test_tinh_lai_dung_he_so_du_tru_trong_ban_ghi(self):
        """
        Quan trong: ban ghi luu r = 0.30 thi tinh lai PHAI dung 0.30, khong
        duoc lay gia tri mac dinh hien tai. Do moi la "dung cau hinh hom do".
        """
        r = evaluate("M-002", created_at=LUC_8H, reserve_factor=0.30,
                     **{**GOC, "soc": 0.30})
        assert r.versions["reserve_factor"] == 0.30
        lai = replay(r)
        assert lai.r_min == pytest.approx(0.30)
        assert lai.verdict == r.verdict

    def test_tinh_lai_tat_dinh(self):
        r = _rec()
        a, b = replay(r), replay(r)
        assert a.verdict == b.verdict and a.reasons == b.reasons


# ---------------------------------------------------------------------------

class TestOutcome:
    """
    Truong ket cuc ghi DOC LAP voi khuyen nghi — P§4.2.

    Neu he thong bao FLY roi tu ghi "thanh cong" thi no tu cham diem chinh no
    va luon duoc 100 %.
    """

    def test_mac_dinh_la_khong_biet(self):
        assert _rec().outcome == OUTCOME_UNKNOWN

    def test_khong_suy_ket_cuc_tu_phan_quyet(self):
        """FLY khong tu dong thanh COMPLETED; NO_FLY khong tu dong thanh NOT_FLOWN."""
        assert _rec().outcome == OUTCOME_UNKNOWN
        assert _rec(soc=0.25).outcome == OUTCOME_UNKNOWN

    @pytest.mark.parametrize("kq", [
        OUTCOME_UNKNOWN, OUTCOME_COMPLETED, OUTCOME_ABORTED, OUTCOME_NOT_FLOWN,
    ])
    def test_ghi_duoc_moi_ket_cuc_hop_le(self, kq):
        assert record_outcome(_rec(), kq).outcome == kq

    def test_ket_cuc_la_bi_tu_choi(self):
        with pytest.raises(ValueError, match="ket cuc khong hop le"):
            record_outcome(_rec(), "THANH_CONG")

    def test_ket_cuc_co_the_nguoc_voi_phan_quyet(self):
        """
        He thong bao FLY nhung chuyen bi huy — phai ghi duoc. Day chinh la du
        lieu dang gia nhat de danh gia he thong ve sau.
        """
        r = record_outcome(_rec(), OUTCOME_ABORTED, "gio giat ngoai du bao")
        assert r.verdict == "FLY"
        assert r.outcome == OUTCOME_ABORTED

    def test_khong_sua_ban_ghi_goc(self):
        goc = _rec()
        record_outcome(goc, OUTCOME_COMPLETED)
        assert goc.outcome == OUTCOME_UNKNOWN


# ---------------------------------------------------------------------------

class TestInv6NoModel:
    """INV-6 — D3 phai la cong thuc va luat, khong co gi duoc huan luyen."""

    def test_khong_co_mo_hinh_hoc_may_trong_d3(self):
        assert scan_for_learned_models() == []

    def test_phep_quet_bat_duoc_vi_pham_that(self, tmp_path, monkeypatch):
        """
        Mot phep kiem luon bao "dat" thi vo dung. Test nay dung mot module gia
        co .fit() that de chac rang phep quet co tac dung.
        """
        import src.workflow_state as ws

        src = tmp_path / "src"
        src.mkdir()
        (src / "gia.py").write_text(
            "from sklearn.linear_model import Ridge\n"
            "def huan_luyen(X, y):\n"
            "    m = Ridge()\n"
            "    m.fit(X, y)\n"
            "    return m\n", encoding="utf-8")
        monkeypatch.setattr(ws, "REPO_ROOT", tmp_path)

        vp = ws.scan_for_learned_models(("gia.py",))
        assert any(".fit()" in v for v in vp)
        assert any("sklearn" in v for v in vp)

    def test_khong_bao_nham_vi_van_ban_giai_thich(self, tmp_path, monkeypatch):
        """
        Chu thich va chuoi ky tu nhac toi .fit() khong duoc tinh la vi pham.
        Chinh src/workflow_state.py chua mau regex r"\\.fit\\s*\\(" duoi dang
        chuoi — neu khong bo chuoi truoc khi quet thi no se tu bao chinh no.
        """
        import src.workflow_state as ws

        src = tmp_path / "src"
        src.mkdir()
        (src / "sach.py").write_text(
            '"""Module nay KHONG goi .fit() o dau ca."""\n'
            "# khong duoc dung .fit() trong D3\n"
            'MAU = r"\\.fit\\s*\\("\n'
            "def cong(a, b):\n"
            "    return a + b\n", encoding="utf-8")
        monkeypatch.setattr(ws, "REPO_ROOT", tmp_path)

        assert ws.scan_for_learned_models(("sach.py",)) == []

    def test_giao_thuc_khai_dung(self):
        from src.decision_rules import load_protocol
        assert load_protocol()["foundation"]["d3_contains_no_learned_model"] is True
