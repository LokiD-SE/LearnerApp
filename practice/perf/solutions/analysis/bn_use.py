"""USE method on the practice target: utilization, saturation and errors for one resource.

The resource here is the target's worker pool. ``GET /metrics`` reports ``in_flight`` (requests being served)
and ``waiting`` (requests queued for a worker); the pool size is the target's ``capacity``.
"""

USE_BUSY = 0.70  # Gregg: "High utilization (eg, beyond 70%) can begin to be a problem"
QUEUE_NOISE = 0.5  # the queue is sampled: a mean below half a request is a request caught between arriving and starting


def utilization(samples, capacity):
    """Mean of in_flight / capacity over the samples (0.0 to 1.0, rounded to 3 places; 0.0 for no samples)."""
    if not samples:
        return 0.0
    return round(sum(s["in_flight"] for s in samples) / len(samples) / capacity, 3)


def saturation(samples):
    """Mean queue length: the mean of ``waiting`` over the samples (rounded to 2 places; 0.0 for no samples)."""
    if not samples:
        return 0.0
    return round(sum(s["waiting"] for s in samples) / len(samples), 2)


def use_findings(util, sat, errors):
    """What to write down for one resource, errors first (they are the quickest to read):
    "errors" if errors > 0, "saturated" if sat >= 0.5, "high-utilization" if util >= 0.70.
    An empty list means: low utilization, no saturation, no errors."""
    findings = []
    if errors > 0:
        findings.append("errors")
    if sat >= QUEUE_NOISE:
        findings.append("saturated")
    if util >= USE_BUSY:
        findings.append("high-utilization")
    return findings


def limiting(resources):
    """The name of the resource most likely to limit throughput, or None.

    ``resources`` maps a name to ``{"utilization": u, "saturation": s, "errors": e}``. Only a resource that is
    saturated or highly utilized is a candidate (errors alone are a finding, not a bottleneck). The longest
    queue wins; a tie goes to the higher utilization, then to the name that sorts first."""
    candidates = []
    for name, r in resources.items():
        findings = use_findings(r["utilization"], r["saturation"], r["errors"])
        if "saturated" in findings or "high-utilization" in findings:
            candidates.append((-r["saturation"], -r["utilization"], name))
    return min(candidates)[2] if candidates else None
