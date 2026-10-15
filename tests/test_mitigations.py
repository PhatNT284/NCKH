"""
Test cho src/mitigations.py — bien phap giam thieu cho CONDITIONAL.

Hien thuc hoa tieu chi Muc 12.1: "conditional verdicts require an explicit
mitigation", va bat bien INV-7.
"""

from __future__ import annotations

import pytest

from src.decision_rules import (
    CONDITIONAL, FLY, NO_FLY, VERDICT_ORDER, assess, load_protocol,
)
from src.mitigations import (
    GROUP_A, GROUP_B, apply_mitigation, catalogue, propose,
)

# Nhiem vu sat nguong — CONDITIONAL
SAT_NGUONG = dict(payload_g=250, speed_commanded_ms=8, altitude_m=50,
                  distance_2d_m=472, wind_forecast_ms=3.0, ambient_temp_c=15,
                  soc=0.28, soh=0.95, e_required_Wh=22.0)


def _uoc_luong(kw: dict) -> float:
    """Xap xi tuyen tinh tu he so Ridge — chi dung trong test."""
    return (22.0
            + 0.008121 * (kw["payload_g"] - 250)
            + 0.235256 * (kw["speed_commanded_ms"] - 8)
            - 0.001305 * (kw["distance_2d_m"] - 472))


# ---------------------------------------------------------------------------

class TestActionable:
    """Muc 12.1 — CONDITIONAL chua co bien phap thi chua thuc thi duoc."""

    def test_conditional_khong_bien_phap_chua_thuc_thi_duoc(self):
        d = assess(**SAT_NGUONG)
        assert d.verdict == CONDITIONAL
        assert d.actionable is False

    def test_conditional_co_bien_phap_thi_thuc_thi_duoc(self):
        d = assess(**SAT_NGUONG, mitigation_applied="M1")
        assert d.verdict == CONDITIONAL
        assert d.actionable is True

    def test_fly_luon_thuc_thi_duoc(self):
        assert assess(**{**SAT_NGUONG, "soc": 0.5}).actionable is True

    def test_no_fly_khong_bao_gio_thuc_thi_duoc(self):
        """Bien phap KHONG duoc dung de lat NO_FLY — §4.6."""
        d = assess(**{**SAT_NGUONG, "soc": 0.20}, mitigation_applied="M1")
        assert d.verdict == NO_FLY
        assert d.actionable is False

    def test_bien_phap_khong_lat_duoc_vi_pham_luat_cung(self):
        d = assess(**{**SAT_NGUONG, "soc": 1.0, "wind_forecast_ms": 14.0},
                   mitigation_applied="M3")
        assert d.verdict == NO_FLY
        assert d.actionable is False

    def test_insufficient_data_khong_thuc_thi_duoc(self):
        d = assess(**{**SAT_NGUONG, "soc": None}, mitigation_applied="M1")
        assert d.actionable is False

    def test_bien_phap_duoc_ghi_vao_ket_qua(self):
        assert assess(**SAT_NGUONG, mitigation_applied="M2").mitigation_applied == "M2"


class TestCatalogue:
    """Danh muc bien phap."""

    def test_du_bay_bien_phap(self):
        ids = [m.id for m in catalogue()]
        assert ids == [f"M{i}" for i in range(1, 8)]

    def test_chia_hai_nhom(self):
        c = catalogue()
        assert {m.group for m in c} == {GROUP_A, GROUP_B}
        assert [m.id for m in c if m.group == GROUP_B] == ["M5", "M6", "M7"]

    def test_nhom_b_can_ham_du_bao(self):
        for m in catalogue():
            assert m.needs_estimator == (m.group == GROUP_B)

    def test_moi_bien_phap_khai_doi_cai_gi(self):
        """
        §2.3: bien phap phai doi NHU CAU NANG LUONG hoac RANG BUOC. Truong
        `changes` buoc nguoi them bien phap moi phai noi ro no doi cai gi.
        """
        for m in catalogue():
            assert m.changes and len(m.changes) > 10


class TestInv7:
    """INV-7 — moi bien phap de xuat PHAI cai thien duoc phan quyet."""

    def test_moi_de_xuat_deu_cai_thien_that(self):
        dx, _ = propose(SAT_NGUONG, estimator=_uoc_luong)
        assert dx, "khong de xuat gi cho mot nhiem vu CONDITIONAL"
        for p in dx:
            assert (VERDICT_ORDER.index(p.after)
                    > VERDICT_ORDER.index(p.before)), f"{p.mitigation.id} vo dung"

    def test_de_xuat_kiem_lai_duoc_bang_apply(self):
        """Chay thu trong propose() va apply() phai cho cung ket qua."""
        dx, _ = propose(SAT_NGUONG, estimator=_uoc_luong)
        for p in dx:
            lai = apply_mitigation(SAT_NGUONG, p.mitigation.id,
                                   estimator=_uoc_luong)
            assert lai.verdict == p.after

    def test_nhiem_vu_da_fly_thi_khong_de_xuat_gi(self):
        """Khong co gi cai thien duoc nua thi khong duoc bay ra bien phap."""
        dx, _ = propose({**SAT_NGUONG, "soc": 1.0}, estimator=_uoc_luong)
        assert dx == []

    def test_quet_192_cau_hinh_khong_de_xuat_vo_dung(self):
        """
        INV-7 tren du lieu that: quet moi chuyen bay o muc SoC sat nguong,
        bao dam khong bien phap nao duoc de xuat ma lai vo dung.
        """
        from src.evaluation_decision import _mission_kwargs, load_missions

        df = load_missions()
        n = 0
        for row in list(df.itertuples())[:40]:
            kw = _mission_kwargs(row, 0.27, 0.95, 15.0)
            kw.pop("profile", None)
            goc = assess(**kw)
            dx, _ = propose(kw, estimator=_uoc_luong)
            for p in dx:
                if VERDICT_ORDER.index(p.after) <= VERDICT_ORDER.index(goc.verdict):
                    n += 1
        assert n == 0


class TestGroupB:
    """Nhom B doi nhu cau nang luong nen BAT BUOC du bao lai."""

    def test_khong_co_ham_du_bao_thi_bo_qua_va_bao_ro(self):
        dx, cb = propose(SAT_NGUONG)
        assert all(p.mitigation.group == GROUP_A for p in dx)
        assert len(cb) == 3
        for m in ("M5", "M6", "M7"):
            assert any(m in c for c in cb), f"{m} bi bo qua im lang"

    def test_apply_nhom_b_khong_co_ham_du_bao_thi_bao_loi(self):
        """
        Im lang giu nguyen E_required cu la bay nguy hiem nhat o day: giam tai
        ma khong du bao lai thi phan quyet dua tren con so sai.
        """
        with pytest.raises(ValueError, match="phai truyen `estimator`"):
            apply_mitigation(SAT_NGUONG, "M5")

    def test_apply_nhom_b_co_ham_du_bao_thi_chay(self):
        d = apply_mitigation(SAT_NGUONG, "M5", estimator=_uoc_luong)
        assert d.mitigation_applied == "M5"

    def test_giam_tai_lam_giam_nhu_cau(self):
        d = apply_mitigation(SAT_NGUONG, "M5", estimator=_uoc_luong)
        assert d.e_required_Wh < SAT_NGUONG["e_required_Wh"]

    def test_nhom_a_khong_can_ham_du_bao(self):
        for mid in ("M1", "M2"):
            assert apply_mitigation(SAT_NGUONG, mid).mitigation_applied == mid


class TestApplicability:
    """Bien phap khong ap dung duoc thi khong duoc de xuat."""

    def test_pin_day_thi_khong_de_xuat_sac_them(self):
        dx, _ = propose({**SAT_NGUONG, "soc": 1.0, "e_required_Wh": 60.0})
        assert all(p.mitigation.id != "M1" for p in dx)

    def test_da_dung_tb48d_thi_khong_de_xuat_doi_pin(self):
        dx, _ = propose({**SAT_NGUONG, "battery_type": "TB48D"})
        assert all(p.mitigation.id != "M2" for p in dx)

    def test_tai_0g_thi_khong_giam_duoc_nua(self):
        with pytest.raises(ValueError, match="khong ap dung duoc"):
            apply_mitigation({**SAT_NGUONG, "payload_g": 0.0}, "M5",
                             estimator=_uoc_luong)

    def test_gio_trong_gioi_han_thi_khong_de_xuat_doi_gio(self):
        dx, _ = propose(SAT_NGUONG, estimator=_uoc_luong)
        assert all(p.mitigation.id != "M3" for p in dx)

    def test_ngoai_envelope_thi_de_xuat_rut_tuyen(self):
        xa = {**SAT_NGUONG, "soc": 1.0, "distance_2d_m": 835}
        assert assess(**xa).verdict == CONDITIONAL
        dx, _ = propose(xa, estimator=_uoc_luong)
        assert any(p.mitigation.id == "M7" for p in dx)

    def test_rut_tuyen_go_duoc_nhan_ngoai_suy(self):
        xa = {**SAT_NGUONG, "soc": 1.0, "distance_2d_m": 835}
        assert assess(**xa).extrapolated
        assert not apply_mitigation(xa, "M7", estimator=_uoc_luong).extrapolated

    def test_bien_phap_la_bi_tu_choi(self):
        with pytest.raises(ValueError, match="bien phap khong biet"):
            apply_mitigation(SAT_NGUONG, "M99")


class TestProtocolMitigation:
    """Kiem phan giao thuc."""

    @pytest.fixture(scope="class")
    def protocol(self):
        return load_protocol()

    def test_quy_uoc_cu_ly_la_khu_hoi(self, protocol):
        cfg = protocol["inputs"]["distance_convention"]
        assert cfg["dataset_is"] == "ROUND_TRIP"
        assert cfg["decision_ref"] == "B7"

    def test_envelope_co_hai_cach_doc(self, protocol):
        e = protocol["inputs"]["distance_convention"]["envelope_two_readings"]
        assert e["total_path_m"] == [420, 610]
        assert e["one_way_delivery_m"] == [210, 305]

    def test_khai_bien_phap_bat_buoc(self, protocol):
        cfg = protocol["reserve_and_verdict"]["conditional_mitigation"]
        assert cfg["decision_ref"] == "B8"
        assert "mitigations.py" in cfg["catalogue_ref"]

    def test_du_bay_bat_bien(self, protocol):
        ids = [t["id"] for t in protocol["invariants"]["tests"]]
        assert ids == [f"INV-{i}" for i in range(1, 8)]

    def test_quyet_dinh_b7_b8_duoc_ghi(self, protocol):
        ids = [d["id"] for c in protocol["change_log"]
               for d in c.get("decisions", [])]
        assert "B7" in ids and "B8" in ids
