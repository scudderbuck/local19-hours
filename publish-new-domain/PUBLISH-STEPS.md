# Publish steps for longshorelife.app (v139) — needs Daniel's approval

Do not do any of these until Daniel says yes to this list. This folder is not part of the live GitHub Pages site. Do not put the CNAME file in the `local19-hours` repo root or merge it to `main` there.

## Why a new repo

If a custom domain is set on the current project repo (`scudderbuck/local19-hours`), GitHub treats that domain as canonical for the Pages site. The default address `https://scudderbuck.github.io/local19-hours/` then leaves the old origin (GitHub 301s project-site github.io URLs to the custom domain once that repo has a CNAME; official docs also say a custom domain on a user site is used for every project site under that account). Either way, phones keep saved shifts in localStorage on the old origin, so users would open an empty app.

A custom domain on the user site `scudderbuck.github.io` would also pull project sites (including this one) under longshorelife.app and redirect the github.io URLs. Do not use a user-site setup.

The safe design: create a **separate project repository**, attach `longshorelife.app` only there, and leave `local19-hours` Pages on `https://scudderbuck.github.io/local19-hours/` with the v139 move notice.

## Already done (no further DNS change expected)

Porkbun already has:

- Apex A records for `longshorelife.app` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
- `www` CNAME → `scudderbuck.github.io` (the account host, not a repo path)

Canonical host is the apex `longshorelife.app`. GitHub will redirect `www.longshorelife.app` to the apex when both records and the CNAME file match.

`.app` is on the HSTS preload list, so browsers always use HTTPS. The site will not load until GitHub has issued the certificate and Enforce HTTPS is on.

## Exact steps (all need approval)

1. **Create a new public GitHub repository** under the same account, recommended name `longshorelife` (https://github.com/scudderbuck/longshorelife). Do not name it `scudderbuck.github.io` and do not replace `local19-hours`. A later org named Longshore Life could hide the personal account in the GitHub URL; it is not required for the app URL.

2. **Push the v139 app files** to that new repo's default branch (the same app files as this branch, plus the `CNAME` file from this folder, placed at the **new repo root** as `CNAME` containing only `longshorelife.app`). Do not add that CNAME to `local19-hours`.

3. **Enable GitHub Pages** on the new repo: Settings → Pages → Deploy from the default branch, `/` (root).

4. **Set the custom domain** on the **new repo only**: Settings → Pages → Custom domain → `longshorelife.app` → Save. GitHub may rewrite the CNAME file; keep it as `longshorelife.app`. Optionally verify the domain first (Settings → Pages → Custom domain verification) so nobody else can claim it.

5. **Wait for DNS check + HTTPS certificate** (often minutes, up to 24 hours). Then turn on **Enforce HTTPS**. Required for `.app`. If the cert hangs, remove and re-add the custom domain after confirming DNS with `dig longshorelife.app` (A records to the four 185.199.108–111.153 addresses) and `dig www.longshorelife.app` (CNAME to `scudderbuck.github.io`).

6. **Confirm both sites work independently** before telling users to move:
   - `https://longshorelife.app/` loads the app (www redirects to apex).
   - `https://scudderbuck.github.io/local19-hours/` still loads (no redirect) and shows the move notice.
   - If the old URL redirects, the custom domain was attached to the wrong repo — remove it immediately from `local19-hours` or the user site.

7. **Merge / publish v139 on `local19-hours`** (PR into `main`, same process as earlier versions) so the old address gets the notice and the one-tap move. Do not add a CNAME there. Keep Pages on this project repo as they are today.

8. **Copy or mirror the existing GitHub Actions** (news, vessels, letters) onto the new repo, or later set a deploy that updates both repos. Until that is done, ship and news files on longshorelife.app will go stale.

9. **GoatCounter** stays as-is (`longshorelife.goatcounter.com`). Both origins will count until the old address is eventually retired. Daniel still needs to finish GoatCounter email verification if that is outstanding.

10. **Do not turn off the old site** until people have had time to move. Installed Home Screen icons keep opening the old origin, which is what lets them transfer.


## Icons

The new v8 crane-at-sunset icon is only for `longshorelife.app`. It lives in `icons/` and `manifest-new.json`. The shared `index.html` picks those files when the host is longshorelife.app (or when testing with `?l19site=new`). The new-domain header also uses `img/logo-header-new.png` with a visible Longshore Life wordmark; the old address keeps `img/logo-header.png`.

Leave the existing root files alone when you publish the old address: `icon-192.png`, `icon-512.png`, `favicon.ico`, `img/apple-touch-icon.png`, `img/icon-512-maskable.png`, and `manifest.json`. `https://scudderbuck.github.io/local19-hours/` should keep the current logo. A 512 px store upload file is at `icons/store-512.png`. The new address also uses a single Harry Bridges video splash (`img/bridges-turn.mp4`) with a LONGSHORE LIFE title over the navy above his head; the old address keeps the two still images (`img/splash.jpg` then `img/bridges.jpg`).

## After publish, tell users

- Open the old address once, tap **Move my data to longshorelife.app**, and confirm on the new site.
- Then add Longshore Life to the Home Screen **from longshorelife.app**. The old icon still opens the old site.
- Photos (ship letters, Today's needs, peg boards, ship gear) are not in the JSON move. They stay on the old address until that site's data is cleared.

## What not to do

- Do not set `longshorelife.app` on `scudderbuck/local19-hours`.
- Do not set it on a `scudderbuck.github.io` user site.
- Do not delete or unpublish `local19-hours` Pages in the same week as launch.
- Do not force-push or otherwise skip the usual “Daniel approves publish” step.
