# Security policy

## Reporting a vulnerability

**Do not open a public issue for a security report.**

Open a [private security advisory][advisory]. It is visible only to the maintainers,
lets us discuss a fix before it is public, and needs no email address from you. It is
the same private channel the [Code of Conduct](CODE_OF_CONDUCT.md) uses.

Please include what you were running (version, install extras, CLI or web API), what
you did, what happened, and what you expected. A minimal reproduction helps most.

We aim to acknowledge a report within a week. AlleleForge is maintained by
volunteers; there is no bounty program, and we would rather tell you that plainly
than imply a response time we cannot hold to. Reporters are credited in the
changelog unless they ask otherwise.

## Supported versions

The `0.x` series is pre-1.0 and fixes land on `main`. Security fixes are not
backported; upgrade to the latest release.

## What is in scope

- **The package.** Parsing untrusted input — VCFs, BED and TSV files, FASTA, model
  cards, chain files, benchmark result JSON — and anything that could execute code,
  read files outside the paths you named, or write outside the cache directory.
- **The web API and served frontend.** Authentication, request limits, injection into
  rendered pages, and the job queue.
- **The artifact gates.** Anything that lets an unpinned, unverified, or tampered
  model checkpoint, dataset, or cache entry be used as though it had passed
  verification. Consent bypasses — anything that downloads without the caller's
  say-so — belong here too.
- **Generated leave-behinds.** Reports, oligo tables, and the leaderboard are shared
  with other people; markup or script injected through submitter- or file-supplied
  text is a vulnerability, not a rendering quirk.

## What is not a vulnerability

- **A wrong scientific prediction.** AlleleForge produces uncertain hypotheses for
  research use. An efficiency estimate that turns out wrong at the bench is a
  modeling issue — open an issue, and see [Scope & responsible use](docs/scope.md).
- **The bundled benchmark fixtures being synthetic.** They are stand-ins so the
  harness runs in CI, and they are labeled as such everywhere they appear.
- **An open API on loopback.** The local single-user deployment is open by design;
  see below for what that means and how to change it.

## Deployment notes worth knowing

- **The API is unauthenticated unless you give it a token.** Set
  `ALLELEFORGE_API_TOKEN` and every `/api/*` request (except `/api/health`) must
  carry a matching `X-API-Token` header. `alleleforge.web.api.serve()` additionally
  *refuses* a non-loopback bind without one — but running `uvicorn` against the
  module-level `app`, as the deployment guide and the Docker image do, binds the
  socket itself and cannot consult that guard. On that path the token is the control.
- **Bind loopback unless you mean otherwise.** The bundled `docker-compose.yml` maps
  `127.0.0.1:8000:8000` for that reason.
- **No outbound network calls.** A design request transmits no sequence data
  externally; a test fails if any socket connects during one. Artifact downloads are
  separate, consent-gated, and checksum-verified.
- **Downloads are pinned.** Model checkpoints and datasets are verified against a
  recorded SHA-256 and refused on mismatch. Reaching a download at all requires
  explicit consent (`allow_network`).

[advisory]: https://github.com/clay-good/alleleforge/security/advisories/new
