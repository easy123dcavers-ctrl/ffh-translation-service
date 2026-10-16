"""Isolated FFH translator resource acceptance policy: >=20% free RAM.

For an exactly 512 MiB memory cgroup, peak must be <=409.6 MiB.
Check using integers so reported decimal rounding cannot manufacture a pass.
This is an acceptance gate, not a prediction of actual production memory.
"""
MEMORY_HEADROOM_MIN_PERCENT = 20
EXPECTED_CGROUP_MIB = 512
MIB = 1024 * 1024

def memory_gate(peak_bytes, limit_bytes, oom_kills):
    if type(peak_bytes) is not int or type(limit_bytes) is not int or type(oom_kills) is not int:
        raise TypeError("Cgroup memory metrics must be exact integers")
    if peak_bytes < 0 or limit_bytes != EXPECTED_CGROUP_MIB * MIB or oom_kills < 0:
        raise ValueError("Invalid cgroup limit or resource metrics")
    return oom_kills == 0 and peak_bytes * 5 <= limit_bytes * 4
