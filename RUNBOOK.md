Status = what we are doing with the asset in the EA program.
Eligibility = whether the asset is allowed to be in the EA program at all (by rules, policy, vendor constraints).

So for your question:

Terminated → Eligibility should be Ineligible

Not “Unknown.” Not “Eligible.”
Terminated means the vendor/program has locked the door and thrown away the key. Even if the hardware is still sitting in a rack humming sadly, the EA relationship is over for that asset. So eligibility becomes a hard no.

That’s different from Excluded, which is just “we chose not to include it (yet).”

Now let’s write the lifecycle documentation cleanly for end users.

Asset Program Coverage Lifecycle (EA Management)

This section defines how assets progress through coverage states within the Enterprise Agreement (EA) program, and how eligibility is represented.

The system uses two fields:

Status: Operational lifecycle state of the asset in the EA program

Eligibility: Whether the asset is permitted to participate in the EA program

These two fields work together to clarify both intent and possibility.

Status Values
Planned

The asset is expected to be added to EA coverage in the future, but is not currently active.

Use this when:

Hardware has been delivered but not yet enrolled

Coverage will begin at a later date

EA onboarding is pending

Planned assets may be added later without restriction.

Typical Eligibility: Eligible

Active

The asset is currently covered under the EA program.

Use this when:

The asset is successfully enrolled

Support/coverage is in effect

The asset contributes to EA consumption/tracking

Typical Eligibility: Eligible

Excluded

The asset is intentionally not part of EA coverage, but may be included later if circumstances change.

Use this when:

The asset is out of scope for now

Coverage is handled another way

The organization is deferring enrollment

Excluded assets are not locked out — they are simply not included today.

Typical Eligibility: Eligible

Terminated

The asset was previously part of EA coverage but has been permanently removed and cannot be re-added.

Use this when:

Cisco/vendor has closed the record

Contractual rules prevent reinstatement

The asset has exited EA permanently

This is a one-way state.

Once terminated:

The asset cannot return to Planned or Active

It is permanently non-participating

Future coverage must occur outside EA (if possible)

Typical Eligibility: Ineligible

Important: Terminated is fundamentally different from Excluded.
Excluded is reversible. Terminated is not.

Eligibility Values
Unknown

Eligibility has not yet been determined.

Use this when:

The asset has not been assessed

Data is incomplete

Vendor status is unclear

This should be temporary.

Eligible

The asset is allowed to be included in the EA program.

Eligibility does not mean it is included — only that it can be.

Eligible assets may be:

Planned

Active

Excluded

Ineligible

The asset cannot be included in the EA program due to vendor, contractual, or policy restrictions.

Use this when:

The asset is not supported

The vendor disallows enrollment

The asset has been permanently removed (terminated)

Ineligible assets should not return to Active or Planned states.

Recommended Status + Eligibility Combinations

Here’s the sane truth-table:

Planned + Eligible → Expected future enrollment

Active + Eligible → Covered right now

Excluded + Eligible → Optional, can be added later

Terminated + Ineligible → Permanently removed, cannot return

Other combinations should generally not occur unless you have an edge case.

Lifecycle Progression (Typical Flow)

Most assets follow one of these paths:

Normal onboarding:
Planned → Active

Deferred participation:
Planned → Excluded → Active (later)

Permanent exit:
Active → Terminated (and eligibility becomes Ineligible)

Key Rule (the one users must remember)

Eligibility answers: “Is this asset allowed to be in EA?”
Status answers: “What are we doing with it?”

And:

Termination is a hard stop. Exclusion is a soft pause.

If you bake that into your plugin logic, you’ll prevent 90% of future confusion and spreadsheets of doom.

Next step would be adding guardrails in the UI:

Terminated forces Eligibility = Ineligible

Active requires Eligibility = Eligible

Excluded/Planned default to Eligible unless proven otherwise

That way users can’t create weird zombie states like “Active but Ineligible,” which is basically metaphysical nonsense.



Quick Truth Table (the universe in 6 lines)
Scenario	Eligibility	Status
SP hardware (never allowed)	ineligible	excluded
Past EOS, never active	ineligible	excluded
Past EOS, previously active	ineligible	terminated
Supported + allowed, not active yet	eligible	planned
Supported + allowed + contract attached	eligible	active
Missing lifecycle (assumed supported)	eligible	planned
Why excluded vs terminated matters

If you terminate everything EOS, your reports become nonsense:

Terminated should mean “we ended coverage”

Excluded should mean “cannot be covered / not included”

EOS devices are usually excluded, not terminated, unless they were actually active.

if eligibility == "ineligible":
    if status == "active":
        status = "terminated"
        effective_end_date = eos_date
    else:
        status = "excluded"