# Library integration research

## Goal
Build one tool that can log in to several Swedish library accounts and produce a combined summary of:

- current loans
- due dates / overdue status
- reservations / holds
- pickup location or queue status when available

Target libraries:

- Lerum
- Partille
- Mölnlycke / Härryda kommun
- Alingsås

## Overall conclusion
The easiest path is **not** to start from undocumented backend APIs unless they are clearly exposed by the library system.

Instead, use the web account flows of each library system:

1. **Koha** for Partille and Alingsås
   - best candidate for direct HTTP session emulation
   - server-side rendered pages with predictable login/account URLs
   - likely easiest to scrape reliably without full browser automation

2. **Axiell Arena** for Härryda / Mölnlycke
   - likely possible with HTTP session emulation, but more stateful and less pleasant than Koha
   - may require handling Liferay/Arena login tokens and account pages
   - browser automation may be simpler than reverse-engineering every request

3. **VuFind-based portal** for Lerum
   - custom integration on top of VuFind and an ILS login flow
   - likely possible with HTTP session emulation
   - may expose some AJAX/JSON endpoints, but account extraction should probably start from normal HTML pages

Recommended strategy:

- **Phase 1:** implement account retrieval through normal web login and HTML parsing.
- **Phase 2:** if any library turns out brittle, upgrade only that integration to browser automation.
- **Phase 3:** if a stable internal JSON/API endpoint is discovered during implementation, switch that specific library to the cleaner endpoint.

---

## Library-by-library findings

### 1) Lerum
- Municipality site points to: `https://bibliotek.lerum.se/`
- Login page found at: `https://bibliotek.lerum.se/vufind/MyResearch/UserLogin`
- Observed tech:
  - **VuFind**-style routes (`/vufind/...`)
  - Apache
  - session cookie `JSESSIONID`
  - hidden CSRF field in login form

#### Observed login form
The login form posts to:
- `POST /vufind/MyResearch/Home`

Observed fields:
- `username`
- `password`
- `auth_method=ILS`
- `csrf=<token>`

Visible labels indicate credentials are:
- `Lånekortnummer / Personnummer (ÅÅMMDDXXXX)`
- `Lösenord / PIN (fyra siffror)`

#### Likely approach
**Best first approach:** direct HTTP session emulation.

Reasoning:
- standard HTML form login
- CSRF token is visible in page source
- account area seems to live under normal VuFind routes
- less likely to require JS-heavy browser automation than Arena

#### Things to verify later
- exact page(s) for:
  - current loans
  - holds / reservations
  - renewals
- whether these pages are server-rendered HTML or backed by reusable JSON endpoints
- whether due dates are easy to parse from markup
- whether anti-bot protections appear after repeated logins

#### Assessment
- **Feasibility:** High
- **Preferred integration style:** HTTP + cookie jar + HTML parsing
- **Browser automation needed?:** Probably not

---

### 2) Partille
- Municipality site points to: `https://bibliotekskatalog.partille.se/`
- Account page/login page found at:
  - `https://bibliotekskatalog.partille.se/cgi-bin/koha/opac-user.pl`
- Observed tech:
  - **Koha** OPAC
  - Apache/Ubuntu
  - session cookie `CGISESSID`
  - `meta name="generator" content="Koha"`

#### Observed login form
The login form posts to:
- `POST /cgi-bin/koha/opac-user.pl`

Observed fields:
- `login_userid`
- `login_password`
- `koha_login_context=opac`
- `op=cud-login`
- `csrf_token`

Observed account-related routes in page HTML:
- `/cgi-bin/koha/opac-account.pl`
- `/cgi-bin/koha/opac-user.pl`
- `/cgi-bin/koha/opac-holdshistory.pl`
- `/cgi-bin/koha/opac-readingrecord.pl`
- `/cgi-bin/koha/opac-messaging.pl`
- `/cgi-bin/koha/opac-passwd.pl`

#### Likely approach
**Best approach:** direct HTTP session emulation.

Reasoning:
- Koha is predictable and well-structured
- login flow is simple and form-based
- loans and holds are usually available from stable OPAC pages
- no immediate need for browser automation

#### Things to verify later
- whether current holds are on `opac-user.pl`, `opac-account.pl`, or another page/tab
- whether reservation queue position is shown in account HTML
- whether language/settings affect DOM shape

#### Assessment
- **Feasibility:** Very high
- **Preferred integration style:** HTTP + cookie jar + HTML parsing
- **Browser automation needed?:** Unlikely

---

### 3) Mölnlycke / Härryda kommun
Mölnlycke belongs to Härryda kommun, and the library site found is:
- `https://bibliotek.harryda.se/`

Relevant pages found:
- login entry: `https://bibliotek.harryda.se/c/portal/login?p_l_id=403082`
- logged-in area: `https://bibliotek.harryda.se/protected/my-account/overview`

Observed tech:
- **Axiell Arena**
- Liferay portal
- `arena-portlet` resources
- `Apache-Coyote`
- `JSESSIONID`
- Liferay login action with `p_auth` token

#### Observed login form
Login form action is a Liferay URL under `/startsida` with action parameters, including:
- `p_p_id=com_liferay_login_web_portlet_LoginPortlet`
- `javax.portlet.action=/login/login`
- `p_auth=<token>`

Observed fields include:
- `_com_liferay_login_web_portlet_LoginPortlet_login`
- `_com_liferay_login_web_portlet_LoginPortlet_password`
- several hidden Liferay control fields

The page also references:
- `/protected/my-account/overview`

#### Likely approach
**Start with HTTP session emulation, but expect more friction.**

Reasoning:
- login is still a normal POST form
- however, Liferay/Arena introduces more moving parts than Koha:
  - `p_auth`
  - hidden form fields
  - portal redirects
  - account pages that may be assembled through Arena portlets

If the account overview and loan/hold pages are easily server-rendered after login, this can still be handled without a browser.

If not, **browser automation may be the pragmatic fallback** for this library.

#### Things to verify later
- exact pages for loans and reservations after login
- whether the account pages render fully in HTML or require JS/XHR after load
- whether Arena exposes stable internal endpoints worth using instead of scraping page HTML
- whether queue position and pickup branch are shown in the overview or sub-pages

#### Assessment
- **Feasibility:** Medium to high
- **Preferred integration style:** Try HTTP first
- **Browser automation needed?:** Possible, more likely here than for Koha

---

### 4) Alingsås
Public library-related sites found:
- `https://arena.alingsas.se/`
- `https://kohaopac.alingsas.se/`

Account/login page found at:
- `https://kohaopac.alingsas.se/cgi-bin/koha/opac-user.pl`

Observed tech:
- **Koha** for the OPAC/account area
- Apache/Ubuntu
- session cookie `CGISESSID`
- `meta name="generator" content="Koha"`

#### Observed login form
The login form posts to:
- `POST /cgi-bin/koha/opac-user.pl`

Observed fields:
- `login_userid`
- `login_password`
- `koha_login_context=opac`
- `op=cud-login`
- `csrf_token`

Observed account-related routes in HTML:
- `/cgi-bin/koha/opac-user.pl`
- `/cgi-bin/koha/opac-shelves.pl`
- `/cgi-bin/koha/opac-suggestions.pl`
- `/cgi-bin/koha/opac-illrequests.pl`

The page source also includes Swedish text that rewrites login labels to:
- `Lånekortsnummer eller personnummer (10 siffror)`
- `Pinkod (4 siffror)`

#### Likely approach
**Best approach:** direct HTTP session emulation.

Reasoning:
- same basic advantages as Partille
- account system is Koha, which should be the easiest integration target of the four
- the separate `arena.alingsas.se` site seems less important for this project than the Koha OPAC account site

#### Things to verify later
- exact URLs or tabs for current loans and holds
- whether any useful data only exists in the Arena frontend instead of Koha
- whether reservation queue position appears in account views

#### Assessment
- **Feasibility:** Very high
- **Preferred integration style:** HTTP + cookie jar + HTML parsing
- **Browser automation needed?:** Unlikely

---

## Cross-library implementation recommendation

### Best first design
Implement each library as a separate adapter with a common output shape, for example:

- library name
- account identifier / nickname
- loans[]
  - title
  - author
  - due date
  - renewable?
  - status
- holds[]
  - title
  - status
  - queue position (if available)
  - pickup location (if available)
  - expiry / last pickup date (if available)

### Integration priority
1. **Partille** (Koha)
2. **Alingsås** (Koha)
3. **Lerum** (VuFind + ILS login)
4. **Härryda / Mölnlycke** (Arena/Liferay)

This order should de-risk the project quickly by getting two likely-easy integrations first.

---

## API vs webpage emulation

### Public/official APIs
No obvious public borrower-account API was identified from this initial research.

That means the practical assumption should be:
- **there is no supported public API for account data**, or
- it exists only as undocumented/internal endpoints used by the web UI

### Recommended default
Use **web login + session cookies + HTML parsing** as the baseline approach.

Why:
- available now
- closest to what users already do manually
- works even when there is no official API
- especially suitable for Koha and likely also for Lerum

### When to prefer browser automation
Use Playwright/browser automation only if:
- login depends on JS-generated state that is painful to reproduce
- account data is only rendered after client-side requests
- anti-CSRF/portal behavior becomes too brittle for plain HTTP

At the moment, **Härryda/Mölnlycke is the strongest candidate** for browser automation if HTTP-based integration becomes annoying.

---

## Suggested next step
When coding starts:

1. prototype **Partille** login and extraction first
2. reuse the same approach for **Alingsås**
3. then inspect the logged-in pages for **Lerum**
4. finally test whether **Härryda/Mölnlycke** works cleanly via HTTP or needs browser automation

## Confidence note
This is an initial reconnaissance based on publicly reachable pages and page structure, not a full logged-in flow test. The system identifications are strong, but exact account page layouts and hidden internal endpoints still need verification during implementation.
