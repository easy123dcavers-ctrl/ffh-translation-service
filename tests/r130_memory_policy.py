"""R130 disposable-only policy: user-authorized >=10% reserve under 512 MiB.

Do not replace R125/R129 20% baseline. Exact integers avoid rounded false passes.
A memory PASS alone never implies stable runtime or production certification.
"""
MEMORY_HEADROOM_MIN_PERCENT = 10
EXPECTED_CGROUP_MIB = 512
MIB = 1024 * 1024

def memory_gate(peak_bytes, limit_bytes, oom_kills):
    if type(peak_bytes) is not int or type(limit_bytes) is not int or type(oom_kills) is not int:
        raise TypeError("Cgroup memory metrics must be exact integers")
    if peak_bytes < 0 or limit_bytes != EXPECTED_CGROUP_MIB * MIB or oom_kills < 0:
        raise ValueError("Invalid cgroup limit or resource metrics")
    return oom_kills == 0 and 10 * peak_bytes <= 9 * limit_bytes
