import re
import math

def parse_time_to_seconds(time_str):
    if time_str is None:
        return None
    if m := re.match(r"^(\d+)s$", time_str):
        return int(m.group(1))
    if m := re.match(r"^(\d{1,2}):(\d{2})$", time_str):
        return int(m.group(1)) * 60 + int(m.group(2))
    if m := re.match(r"^(\d+):(\d{2}):(\d{2})$", time_str):
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return None

def format_time(seconds):
    if seconds is None or (isinstance(seconds, float) and math.isnan(seconds)):
        return "-"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"

def format_distance(meters):
    return f"{meters / 1000:.1f} km" if meters >= 1000 else f"{int(meters)} m"

def format_speed_mps_to_kmh(speed_mps):
    return f"{speed_mps * 3.6:.1f} km/h" if speed_mps else "-"

def estimate_power_for_time(distance_m, avg_grade_pct, time_s, mass_kg=70, crr=0.004, cda=0.25, air_density=1.225, drivetrain_eff=0.975):
    if time_s is None or time_s == 0:
        return None
    speed = distance_m / time_s
    grade = avg_grade_pct / 100
    g = 9.81
    f_gravity = mass_kg * g * math.sin(math.atan(grade))
    f_roll = mass_kg * g * math.cos(math.atan(grade)) * crr
    f_air = 0.5 * air_density * cda * speed**2
    total_force = f_gravity + f_roll + f_air
    return round((total_force * speed) / drivetrain_eff)

def format_checkbox(val):
    return "✔️" if val else "❌"
