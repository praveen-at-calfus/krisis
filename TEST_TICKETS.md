# KRISIS — Demo & test tickets

A curated set covering every category, the required edge cases, robustness cases,
disambiguation, and the behavioral features. Each ticket lists the scenario it exercises
and the expected result.

Team routing: access_iam → Identity and access · infra_outage → Infrastructure operations ·
ci_cd → Platform engineering · security → Security team · dev_tooling → Developer experience ·
hardware → Hardware support · unclassified → Triage.

---

## Clear cases — category coverage + priority spread

1. **infra_outage · High**
   > Since about 9:15 this morning the entire production API has been returning 500s for every customer. The status page is red, health checks fail across all regions, and there's no workaround — the whole platform is effectively down.

2. **access_iam · Medium**
   > I've been locked out of my account since I changed my password last night. Every login says 'invalid credentials' and I can't get into any of my tools. As far as I know it's just me.

3. **ci_cd · High**
   > Our Jenkins deployment pipeline has been stuck for an hour and nobody on the team can ship to production — the deploy job hangs at artifact upload and times out.

4. **hardware · Low**
   > There's a single dead pixel in the top-right corner of my external monitor. It's not affecting my work, just annoying — a replacement whenever convenient would be great.

5. **dev_tooling · Low**
   > VS Code freezes for 20–30 seconds whenever I open our monorepo. I can still work from the terminal, but it's slowing me down. Just my machine.

---

## Required edge cases

6. **Angry tone (must NOT inflate priority)** → access_iam · **Medium**
   > THIS IS COMPLETELY RIDICULOUS. I've been waiting THREE DAYS and NOTHING works!!! I still can't get into the shared analytics dashboard and NOBODY has helped me. Fix it NOW.

   *One person blocked → Medium; the rage doesn't change it.*

7. **Very short / vague** → unclassified · **Medium** · needs-review
   > it's broken

8. **Ambiguous (fits two categories)** → access_iam · **Medium**
   > I can't push my code — the CI pipeline keeps rejecting my commits saying my SSH key is unauthorized.

   *Reasoning should tie-break: root cause is a credential, not a pipeline defect.*

---

## Robustness edge cases

9. **Non-English (Spanish)** → access_iam · **Medium**
   > No puedo acceder a mi cuenta de correo, la contraseña no funciona y necesito entrar para una reunión en una hora.

10. **Very long / rambling** → infra_outage · **High**
    > Hi team, flagging something that's been getting worse since this morning. Around 9am our shared staging environment got slow; by 10 several teammates on the payments squad couldn't reach it at all. We cleared caches, reconnected the VPN, restarted machines — nothing helped. The health dashboard shows the staging DB unreachable and the API gateway throwing gateway timeouts for everyone on the floor. This blocks the whole squad from testing Friday's release and QA can't run their suites either. There's no workaround we can find. Could infra take a look ASAP? Happy to hop on a call and screen-share. Thanks so much.

11. **Empty / blank** → **422 / UI warning** — submit an empty box (tests the guard, no crash).

12. **Oversized** → **422** — paste anything over ~20,000 characters (rejected cleanly; normal long input is truncated).

---

## Disambiguation — the "failure wins" rule

13. **Access *system* down** → infra_outage · **High** (not access_iam)
    > The whole SSO / access-control system seems to be down — nobody across the company can log into any internal app right now. It's not just me; the login page itself times out.

    *Contrast with #2: "my access is blocked" = individual → access_iam; "the access system is down" = outage → infra_outage.*

14. **Security auto-High override** → security · **High**
    > I got an email that looked like IT asking me to 'reverify' my password. I clicked the link and entered my credentials before realizing it was fake — I think my account may be compromised.

---

## Feature triggers (behavioral demo)

15. **Semantic cache** — submit back-to-back; the 2nd should show **♻️ answer reused**:
    - a) My corporate VPN keeps disconnecting every couple of minutes and I have to reconnect constantly to keep working.
    - b) My corporate VPN keeps disconnecting every couple of minutes and I have to reconnect over and over just to keep working.

    *If it doesn't reuse, they're just under the 0.92 threshold — lower `CACHE_THRESHOLD` to demo.*

16. **Incident clustering** — submit these three in a row (within 30 min) → 🚨 alarm on the Dashboard (security spike):
    - a) Someone's trying to brute-force the admin login — hundreds of failed attempts in the logs.
    - b) We're seeing a flood of suspicious login attempts on the customer portal from unknown IPs.
    - c) Another wave of failed logins hitting our SSO — looks coordinated, likely a botnet.

17. **Low-confidence / needs-review** → flagged for a human
    > hey can someone look at the thing from yesterday? it's still not right.

---

## Suggested demo order
1 (clear High) → 6 (angry stays Medium) → 8 (ambiguous — read the reasoning) → 13 vs 2 (failure-wins contrast) → 15 (cache reuse) → 16×3 (incident alarm) → 7 (vague → needs review) → Dashboard (time saved, cost, needs-review count).
