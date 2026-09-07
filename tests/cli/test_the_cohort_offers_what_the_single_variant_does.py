"""A shipped requirement with nothing keeping it true.

`openspec/specs/cli/spec.md`: "Every option `aforge design` accepts SHALL be accepted by
`aforge batch`, except those that shape a single rendered document, which the cohort path
does not produce. A cohort is where a trained model or a PAM-flexible fallback matters
most, and an option honoured only through a config file is invisible from `--help`."

The parity was established once and guarded by nothing. Every option added to `design`
since then had to be copied to `batch` by hand, and the failure mode is silent: the flag
simply does not exist on the cohort command, which is the surface where it matters more.

The same requirement holds for the web shell, where `POST /api/design` and `POST
/api/batch` build their calls separately — and where this session watched the drift happen
in real time: a `chromatin_track` field landed on `DesignRequest` and not `BatchRequest`,
and the cohort endpoint went on running reference-only after the population source was
wired into the single-variant one.

The exemptions are the render-shaping options a cohort has no single document for, plus
each command's own input argument. Each is checked to still exist, so the list cannot rot
into excusing options nobody has.
"""

from __future__ import annotations

import inspect

from alleleforge.cli import main as cli
from alleleforge.web.api.models import BatchRequest, DesignRequest

#: `design` options a cohort legitimately lacks: they shape one rendered document
#: (`--format`, `--out`, `--render-candidates`) or name the single input.
#: `vector_scheme` picks the Type IIS enzyme the *report's* oligo screen runs against,
#: and the cohort path writes raw ranked menus — it builds no oligos at all, so there
#: is nothing for a vector to screen. (Giving a cohort run cloning oligos is its own
#: piece of work; until it has them this is an absence, not a parity gap.)
_CLI_EXEMPT = {"fmt", "out", "render_candidates", "variant", "vector_scheme"}

#: The same, for the request models: `render_candidates` shapes one render, the two
#: commands name their input differently (`variant` / `variants`), and `vector_scheme`
#: has no cohort oligos to screen.
_WEB_EXEMPT = {"render_candidates", "variant", "vector_scheme"}


def test_every_design_option_is_offered_by_batch() -> None:
    design = set(inspect.signature(cli.design).parameters)
    batch = set(inspect.signature(cli.batch).parameters)
    missing = design - batch - _CLI_EXEMPT
    assert not missing, (
        f"`aforge design` accepts {sorted(missing)} and `aforge batch` does not. A cohort "
        "is where these matter most; add them, or exempt them with a reason."
    )


def test_every_design_request_field_is_offered_by_batch() -> None:
    missing = set(DesignRequest.model_fields) - set(BatchRequest.model_fields) - _WEB_EXEMPT
    assert not missing, (
        f"`DesignRequest` carries {sorted(missing)} and `BatchRequest` does not, so the "
        "same run is configurable one variant at a time and not as a cohort."
    )


def test_the_exemptions_still_exist() -> None:
    """A list of excuses outlives the things it excuses unless something checks."""
    design_params = set(inspect.signature(cli.design).parameters)
    assert _CLI_EXEMPT <= design_params, sorted(_CLI_EXEMPT - design_params)
    assert _WEB_EXEMPT <= set(DesignRequest.model_fields)
