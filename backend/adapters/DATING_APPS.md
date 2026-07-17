# Dating Apps Catalog

Coverage map for the aggregator. **Implemented** apps have a working adapter in
`backend/adapters/` and are registered. **Planned** apps have a scaffold
"header" file in `backend/adapters/planned/` (unregistered stub with the signup
URL and backend classification) — sign up manually via the URL, then a future
implementer fleshes out the hooks and promotes the file to
`backend/adapters/` (Open/Closed: one new file per app, §3.2).

`web` = usable browser experience → `WebBackendAdapter` (Playwright).
`appium` = native-app-only → `AppiumBackendAdapter` (Android emulator/device).

## Implemented

| App | Backend | Login URL | Status |
|-----|---------|-----------|--------|
| Tinder | web | https://tinder.com/app/login | Adapter written; selectors need live verification |
| Bumble | web | (web login) | Adapter written; selectors need live verification |
| Hinge | appium | (native app) | Adapter written; needs a device/emulator to run |

## Planned (scaffolds in `planned/`, sign up manually)

| App | Backend | Signup / Login URL | Notes |
|-----|---------|--------------------|-------|
| OkCupid | web | https://www.okcupid.com/ | Full web UI; persistent session auth |
| Match.com | web | https://www.match.com/login | Full web platform; email/password or social |
| Plenty of Fish (POF) | web | https://www.pof.com/login | Full web dating platform |
| Coffee Meets Bagel | appium | https://www.coffeemeetsbagel.com/ | Mobile-app-only; FB or phone auth |
| Happn | web | https://app.gethappn.com/account/login | Web platform; phone/Google auth |
| Badoo | web | https://badoo.com/signin | Full web platform; phone/email/social |
| Zoosk | web | https://www.zoosk.com/login | Full web platform; email/phone/social |
| eharmony | web | https://www.eharmony.com/login/ | Compatibility-matching web platform |
| Grindr | web | https://web.grindr.com/login | Web version; needs location + popups |
| HER | appium | https://weareher.com/ | Mobile-only (LGBTQ+ women/non-binary); FB/IG auth |
| Feeld | appium | https://feeld.co/ | Mobile app only; phone/email/social |
| Raya | appium | https://www.rayatheapp.com/ | Invite/approval-only (~8% accept); iOS only |
| The League | web | https://www.theleague.com/join/ | Approval/waitlist; LinkedIn/Facebook required |
| Christian Mingle | web | https://login.christianmingle.com/ | Christian-focused; free signup |
| JDate | web | https://login.jdate.com/ | Jewish dating; free signup |
| Muzz | web | https://muzz.com/us/en/ | Muslim dating/marriage; web + mobile |
| Facebook Dating | web | https://www.facebook.com/dating | FB feature; needs 30+ day-old account |
| Hily | web | https://web.hily.com/ | Web version; phone/email/social signup |
| Boo | web | https://boo.world/ | Inclusive LGBTQ+; dating + social |
| OurTime | web | https://www.ourtime.com/login | Senior dating (50+); free signup |
| Lex | appium | https://www.lex.lgbt/ | Text-based queer personals; mobile only |
| Taimi | web | https://web.taimi.com/ | LGBTQ+ dating; web version |

> URLs and web/appium classifications were gathered by automated research and
> should be re-checked at signup time — dating apps change their login flows and
> web availability frequently (§9 UI drift). Several apps gate signup behind
> phone-OTP, invite/approval, or account-age requirements as noted.
