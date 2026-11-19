# Live service checks

Two ways to settle a claim on a running service instead of a proxy: probe the deployed protocol surface directly, and run the suites against a disposable stack of your own. Both replace a self-report with an answer the service gives back.

## Anonymous protocol probes

A deployment setting is proved by the request a real client makes, not by a config file or a dashboard screenshot. Write the table of setting, request, and expected answer, then run it as a script so it reruns. A hosted OAuth server protected API is the worked example:

| Setting | Request | Passes when |
| --- | --- | --- |
| Protected resource | `GET /.well-known/oauth-protected-resource` | names the API resource and the authorization server origin, not the app origin |
| Unauthenticated API | `POST` the API with no token | 401 with `WWW-Authenticate` naming the metadata URL |
| Authorization server live | `GET <issuer>/.well-known/oauth-authorization-server` | issuer plus the authorization, token, registration, and userinfo endpoints, and the PKCE methods the client needs |
| Dynamic client registration on | `POST` the advertised registration endpoint with a public client, `token_endpoint_auth_method: none` | 201 with a client record |
| Authorization path and site URL | build an `authorize` URL with a PKCE challenge and follow no redirects | 302 to `<app origin>/<authorization path>?authorization_id=...` |
| Sign-in gate on the consent page | `GET` the consent URL with no session | the sign-in prompt, and the return path the page will use |
| A provider enabled | `GET <auth>/authorize?provider=<name>` | 302 to the provider's own host |

Rules that keep the probes honest:

- Register one throwaway client and name it after the check. It is state on someone else's project, so delete it afterwards and report that you created it. Never print a client id, a secret, or a token.
- Keep registration out of a deploy job. Every run would leave another client behind. It is a manual check.
- A probe that needs a session settles nothing past the sign-in gate. Report the interactive remainder as owner-only rather than implying coverage that does not exist.
- Read only the redirect host and path. A query string carries ids that do not belong in notes.
- Probe each setting the request can reach, and say plainly which settings no anonymous request can read. That difference is the report.

## A disposable stack for suites

Integration and contract suites that write to a shared dev database destroy the state a human is using, and two worktrees pointed at one stack corrupt each other. Stand up a second stack from the repository's own CI definition, which is the only setup CI proves.

1. Copy the service definition, meaning config, migrations, seed, and tests, into a scratch directory outside the checkout. Do not edit the shared one.
2. Rewrite the instance or project id, and shift every port by a fixed offset. Confirm the ports are free before you start.
3. Start it, then read its connection values from the CLI into a file with mode `600`. Do not print them.
4. Build and start the app against that stack. Public env values are baked at build time, so build again rather than reuse a build made for the shared stack.
5. Run the suite with its own variables pointing at the disposable stack, then stop the stack and the app process.

Pitfalls that cost a run:

- **Copied config carries absolute URLs.** Auth `site_url`, redirect allow-lists, issuer URLs, and webhook targets still name the app's canonical port. A suite that asserts a redirect to the app origin then fails on the port mismatch, and the failure reads like a product bug. Serve the app on the port the copied config names, or rewrite those URLs too.
- **Parallel worktrees share one dev stack.** Either give each branch its own disposable stack or run the suites one at a time. A `db reset` from one branch pulls the database out from under the other mid-run.
- **A first-run failure in a port, host, or origin assertion is harness setup until proven otherwise.** Fix the harness, rerun, and only then judge the branch. Reporting that failure as a branch defect wastes the run in both directions.
- **Keep the prep in a script** in the scratch directory, with the port offset as a constant, so the next run is one command. An ad-hoc shell sequence gets retyped and drifts.
