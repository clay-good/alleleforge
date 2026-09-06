"""The README stated a design decision that the code had since outgrown.

It said the four file-backed inputs were "deliberately absent" from the web API because a
client-supplied path would be a server-side file-read primitive, and that "that surface
needs server-side configuration like the reference already has". The reasoning was right
and the conclusion had moved: three of the four are now operator-configured exactly as
described, and only `--patient-vcf` stays out — for a different reason, since a personal
genotype is the caller's data rather than the operator's.

A README paragraph explaining why something is missing is the kind of text nobody revisits
when it stops being missing, so this checks the claim instead of trusting it: each source
the README says an operator can configure must have its environment variable read, and the
one it says is absent must really be absent from both request models.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from alleleforge.web.api import app as web_app
from alleleforge.web.api.models import BatchRequest, DesignRequest, OffTargetRequest

_README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

#: Operator-configured file inputs the README promises are reachable over HTTP.
_CONFIGURABLE = ("ALLELEFORGE_GNOMAD_TSV", "ALLELEFORGE_HAPLOTYPES", "ALLELEFORGE_ENCODE_TRACKS")


def test_the_readme_names_the_variables_that_configure_them() -> None:
    for env_var in _CONFIGURABLE:
        assert env_var in _README, f"{env_var} configures the web API and the README omits it"


def test_each_named_variable_is_actually_read() -> None:
    """A documented setting nothing reads is worse than an undocumented one."""
    source = inspect.getsource(web_app)
    for env_var in _CONFIGURABLE:
        assert f'os.environ.get("{env_var}")' in source, f"{env_var} is documented, not read"


def test_the_create_app_arguments_exist() -> None:
    params = set(inspect.signature(web_app.create_app).parameters)
    assert {"reference", "gnomad", "haplotypes", "encode_tracks"} <= params


def test_a_patient_genotype_is_still_not_a_request_field() -> None:
    """The one the README says stays out: caller data, not operator data."""
    for model in (DesignRequest, BatchRequest, OffTargetRequest):
        assert not [f for f in model.model_fields if "patient" in f], model.__name__
    assert "`--patient-vcf` remains absent" in _README


def test_no_request_model_takes_a_filesystem_path() -> None:
    """The premise of the whole arrangement: a client path would be a file-read primitive."""
    for model in (DesignRequest, BatchRequest, OffTargetRequest):
        for name, field in model.model_fields.items():
            assert field.annotation is not Path, f"{model.__name__}.{name} takes a path"
