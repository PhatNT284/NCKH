"""Frozen D2/D3 decisions and two energy references in the same changed world.

Reference demand definitions stay frozen; battery/SoC/SoH/temperature availability
and changed mission features are recomputed. Candidate residual shocks are not
silently injected into either reference. All labels are simulation-derived.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.physics_m100 import G, RHO_AIR, disk_area_m2, fit_efficiency
from src.reference_labeller import scenario_features
from src.uncertainty import INPUT_FIELDS


def label_energy(available, demand, valid, reserve=.2):
    margin = available-demand
    with np.errstate(divide="ignore",invalid="ignore"):
        ratio = margin/demand
    known = valid & np.isfinite(margin) & np.isfinite(demand) & (demand>0)
    labels = np.full(len(available),"unknown",dtype=object)
    labels[known & (margin<=0)]="infeasible"
    labels[known & (margin>0) & (ratio<reserve)]="marginal"
    labels[known & (margin>0) & (ratio>=reserve)]="feasible"
    return labels,ratio


class WorldEvaluator:
    def __init__(self,context):
        self.context=context
        self.efficiency={b:fit_efficiency(b) for b in ("TB47D","TB48D")}
        self.nominal={c["battery_type"]:float(c["nominal_Wh"])
                      for c in context.d5["factors"]["nominal_battery_energy"]["cases"]}
        self.allowance=float(context.d3["energy_required"]["measured_error"]["p95_abs_residual_Wh"])
        self.ref_allowance=float(context.d4["reference_label"]["frozen_numbers"]["uncertainty_allowance_Wh"])
        self.calibration=float(context.d4["reference_label"]["sensitivity_method"]["frozen_numbers"]["calibration_k"])
        self.ref_reserve=float(context.d4["reference_label"]["method"]["reserve_policy_for_reference"]["r"])
        self.primary_reserve=float(context.d5["inherited_baseline"]["decision_policy"]["reserve_ratio"])
        self.profile=context.d5["inherited_baseline"]["aircraft_profile"]["primary_diagnostic"]

    def evaluate(self,frame,*,candidate_demand=None,kappa_override=None):
        frame=frame.reset_index(drop=True).copy()
        n=len(frame)
        raw={name:pd.to_numeric(frame[name],errors="coerce").to_numpy(float) for name in INPUT_FIELDS}
        for name,values in raw.items():frame[name]=values
        battery=frame["battery_type"].to_numpy(object)
        profile=frame["profile"].to_numpy(object) if "profile" in frame else np.full(n,self.profile,dtype=object)
        reserve=(pd.to_numeric(frame["reserve_factor"],errors="coerce").to_numpy(float)
                 if "reserve_factor" in frame else np.full(n,self.primary_reserve))
        mass=np.full(n,np.nan)
        mtow=np.full(n,np.nan)
        for p in ("M100_stock","CMU_instrumented"):
            cfg=self.context.d3["aircraft_profiles"][p]
            for b in self.nominal:
                chosen=(profile==p)&(battery==b)
                base=cfg["airframe_mass_g"]
                base=base[b] if isinstance(base,dict) else base
                mass[chosen]=float(base)+raw["payload_g"][chosen]
                mtow[chosen]=cfg["mtow_g"]
        nominal=np.array([self.nominal.get(b,np.nan) for b in battery])
        eta=np.array([self.efficiency.get(b,np.nan) for b in battery])
        temp=raw["ambient_temp_c"]
        cold,warm=self.context.d3["available_energy"]["kappa_temperature"]["calibrated_range_c"]
        poly=lambda t:.8814+.0091*t-.0001*t*t
        kap=np.where(temp<cold,poly(cold),np.where(temp>warm,1.,np.minimum(1.,poly(temp))))
        if kappa_override is not None:kap=np.broadcast_to(np.asarray(kappa_override,dtype=float),(n,)).copy()
        with np.errstate(invalid="ignore",divide="ignore",over="ignore"):
            x=scenario_features(frame,self.context.d4,list(self.context.model.features)).to_numpy(float)
            prediction=((x-self.context.model.means)/self.context.model.scales)@self.context.model.coefficients+self.context.model.intercept
            required=prediction.copy() if candidate_demand is None else np.broadcast_to(np.asarray(candidate_demand,float),(n,)).copy()
            available=nominal*raw["soc"]*raw["soh"]*kap
            ideal_power=(mass/1000*G)**1.5/np.sqrt(2*RHO_AIR*disk_area_m2())
            duration=raw["distance_2d_m"]/raw["speed_commanded_ms"]
            descent=self.context.d3["hard_rules"]["physics_derived"][0]["descent_rate_ms"]
            landing=ideal_power/eta*raw["altitude_m"]/descent/3600
        finite=np.logical_and.reduce([np.isfinite(v) for v in raw.values()])
        valid=(finite & np.isfinite(required)&(required>0)&np.isfinite(nominal)&np.isfinite(mass)
               &np.isfinite(reserve)&(reserve>=0)&(raw["soc"]>=0)&(raw["soc"]<=1)
               &(raw["soh"]>=0)&(raw["soh"]<=1)&(kap>=0)&(kap<=1)
               &(raw["payload_g"]>=0)&(raw["altitude_m"]>=0)&(raw["wind_forecast_ms"]>=0)
               &(raw["speed_commanded_ms"]>0)&(raw["distance_2d_m"]>0))
        manufacturer={r["id"]:r for r in self.context.d3["hard_rules"]["manufacturer"]}
        wind_limit=float(manufacturer["HR-1"]["check"].split("<=")[-1])
        temp_low,temp_high=[float(t) for t in manufacturer["HR-2"]["check"].split("<=")[::2]]
        speed_limit=float(manufacturer["HR-4"]["check"].split("<=")[-1])
        wind_veto=raw["wind_forecast_ms"]>wind_limit
        mass_veto=(profile!="CMU_instrumented")&(mass>mtow)
        landing_veto=available<landing
        temperature_veto=(temp<temp_low)|(temp>temp_high)
        speed_veto=raw["speed_commanded_ms"]>speed_limit
        veto=wind_veto|mass_veto|landing_veto|temperature_veto|speed_veto
        rules={r["id"]:r["check"].split("<=") for r in self.context.d3["hard_rules"]["project_derived"]}
        distance_out=(raw["distance_2d_m"]<float(rules["PD-1"][0]))|(raw["distance_2d_m"]>float(rules["PD-1"][-1]))
        payload_out=(raw["payload_g"]<float(rules["PD-2"][0]))|(raw["payload_g"]>float(rules["PD-2"][-1]))
        wind_support=self.context.d5["factors"]["wind_magnitude"]["measured_coverage_ms"]
        wind_out=(raw["wind_forecast_ms"]<wind_support[0])|(raw["wind_forecast_ms"]>wind_support[1])
        with np.errstate(divide="ignore",invalid="ignore"):
            ratio=(available-required)/required
            fly_threshold=reserve+self.allowance/required
        verdict=np.full(n,"NO_FLY",dtype=object)
        enough=valid&~veto&(ratio>=reserve)
        verdict[enough]="CONDITIONAL"
        verdict[enough&(ratio>=fly_threshold)&~distance_out&~payload_out]="FLY"
        verdict[~finite]="INSUFFICIENT_DATA"
        verdict[veto]="NO_FLY"
        ref1=prediction+self.ref_allowance
        ref2=self.calibration*ideal_power*duration/3600
        labels1,ratio1=label_energy(available,ref1,valid,self.ref_reserve)
        labels2,ratio2=label_energy(available,ref2,valid,self.ref_reserve)
        return dict(valid=valid,verdict=verdict,prediction=prediction,required=required,available=available,
                    margin=available-required,ratio=ratio,reserve=reserve,
                    slack=available-(1+reserve)*required,kappa=kap,mass_g=mass,landing_Wh=landing,
                    veto=veto,wind_veto=wind_veto,mass_veto=mass_veto,landing_veto=landing_veto,
                    temperature_veto=temperature_veto,speed_veto=speed_veto,
                    distance_extrapolated=distance_out,payload_extrapolated=payload_out,
                    wind_extrapolated=wind_out,temperature_outside_calibration=(temp<cold)|(temp>warm),
                    ref1_demand=ref1,ref2_demand=ref2,ref1_label=labels1,ref2_label=labels2,
                    ref1_ratio=ratio1,ref2_ratio=ratio2)
