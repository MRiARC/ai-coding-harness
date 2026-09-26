"""Offline A/B token benchmark (milestone 5, issue 5.5).

`harness bench` runs the offline fixture end-to-end twice - current code vs a
git ref (or a saved baseline) - and reports the per-agent prompt/completion
delta. Zero credentials: the FakeProvider scripts every model reply and token
counts come from the deterministic estimator, so identical code produces
identical numbers. This is the measuring stick behind the token-reduction
acceptance gates (#60's >=30%, #63's >=50%).
"""
