# Hallo Magic Pizza – Ordering System (Prototype) – PRD

## Original problem statement
Build a TEST VERSION of a professional ordering system for Hallo Magic Pizza (Italian pizzeria, Switzerland, CHF).
Mobile app (iOS/Android) first + architecture for a responsive web ordering site. ONE backend, ONE database, ONE catalog,
ONE order system, ONE restaurant dashboard, ONE kitchen dashboard, ONE admin panel. All orders (iPhone/Android/web) arrive
in the same dashboard in real time. Bilingual FR (default) / DE. No online payment (pay at pickup / delivery). Existing website
hallomagicpizza.ch is read-only reference only (menu, prices, sizes, extras, delivery zones) – never touched.

## User choices
- Restaurant name: Hallo Magic Pizza · Staff area: no protection (test) · Customer accounts: skipped (guest checkout)
- Push: events/in-app status only (real push later) · Design: light & warm (cream / tomato red / olive / terracotta)

## Architecture
- Backend: FastAPI + MongoDB (`/app/backend/server.py`, seed in `seed_data.py`), all routes under `/api`.
  Collections: categories, products, extras, settings, orders, counters, print_jobs.
  Realtime: clients poll (`/api/orders?active=true` every 3s, order tracker every 4s, menu every 8s).
  Printing: PrintNode adapter prepared (`PRINTNODE_API_KEY`, `PRINTNODE_PRINTER_ID` in backend/.env; empty = `simulated`).
  Auto-print on accept, reprint (force), duplicate protection (409 + 10s guard), fields printed / printed_at / print_attempts / print_status.
- Frontend: Expo Router (SDK 57), react-query, keyboard-controller, theme tokens in `src/theme.ts`.
  Customer tabs: Menu / Panier / Commandes / Plus. Product modal, checkout, order tracker.
  Staff: `/staff` dashboard (2-col on tablets ≥900px, modal on phones), `/staff/kitchen`, `/staff/ticket/[id]`, `/staff/admin` (+ product editor, extras, settings).
  Source of each order recorded (ios / android / web).

## Implemented (2026-06)
- Real menu imported as test data: Pizza (26 incl. sizes 32/40/50 cm, gluten-free dough +4 on 32cm, lactose-free +4/7/10), Pizza sans gluten (virtual filter), Créer votre pizza (base + 29 priced ingredients), Piadina & Pasta, Dessert, Boissons (incl. 18+ items with age confirmation).
- Delivery zones + per-NPA minimum order from the current website (Marly 25 … Farvagny 70), editable in admin settings.
- Pizza customization: size, dough, options, remove ingredients, extras (max qty), kitchen note, live price.
- Cart (edit/remove/qty/notes), checkout pickup/delivery, ASAP or scheduled slot, guest details, payment at pickup/delivery.
- Orders: statuses pickup & delivery flows, accept (minutes / confirm requested time / custom exact time), reject with reason, +5/+10/+15 or exact-time change, notifications (FR/DE texts) stored per order, customer tracker with ETA + "time changed" notice.
- Staff dashboard: visual + audio alert on new order, filters, huge action buttons, ticket preview (80 mm monospace), print/reprint.
- Kitchen grid with big typography (removals red, extras green, options terracotta).
- Admin: products list with AVAILABLE/SOLD OUT switch (instant on all clients), bilingual product editor (names, descriptions, price, sizes, ingredients, allergens, photo URL, allowed extras, dough options), extras manager, restaurant settings (closure, pickup/delivery on/off, min order, fee, zones, hours).
- Testing: backend 21/21 pytest (`/app/backend/tests/test_hallo_magic_pizza.py`, run with `-n 0`), frontend E2E passed.

## Implemented (2026-06) – design refinement round 2
- Premium homepage: full-bleed hero + "Commander maintenant" CTA, large Retrait/Livraison selector (shared with checkout), compact category rail, editorial image-first product cards with clear "Personnaliser" / "Ajouter" actions, dark summary card in cart, taller product hero with overlapping sheet, refined tab bar.
- Staff area separated & protected: hidden from customers (small "Accès restaurant" link in Plus tab), PIN gate at `/staff/login` (PIN from `EXPO_PUBLIC_STAFF_PIN` in frontend/.env, default 1234, remembered on device; lock button in dashboard header).
- Direct staff URL: `<preview-url>/staff` (redirects to `/staff/login` until unlocked). Kitchen `/staff/kitchen`, Admin `/staff/admin`.

## Implemented (2026-06) – VAT / TVA & customer receipt
- Fiscal settings (admin → Paramètres → Fiscal / TVA): raison sociale, Route de Chésalles 19, 1723 Marly, Tél. 026 430 00 96, CHE-156.631.035 TVA, standard rate 2.6%, alcohol rate 8.1%, delivery-fee VAT rate.
- Every product and every extra has an editable `vat_rate` (2.6 / 8.1) in admin; alcohol products flagged 18+.
- Orders store a VAT snapshot (per item, per extra, per rate group, totals net/vat/gross, discount allocation prepared). Historical orders never change.
- Customer receipt (80 mm, `/api/orders/{id}/receipt`, staff screen `/staff/receipt/{id}`, print/reprint, simulated PrintNode) – separate from the kitchen ticket. Customer tracker shows "TVA incluse" lines.
- Tests: `/app/backend/tests/vat_scenarios.py` (7 scenarios) and `/app/backend/tests/test_vat_receipt.py`.

## Implemented (2026-06) – age check, customer accounts, product photos
- Alcohol age check (dynamic): product `alcohol_type` = fermented (beer, wine, prosecco -> 16+) | spirits (-> 18+); mixed cart -> 18+. Checkout checkbox is mandatory with 16+/18+ text, order stores `age_required` + `age_confirmed`, kitchen ticket prints "ALCOOL - CONTROLE AGE 16+/18+ / VERIFIER LA PIECE D'IDENTITE", staff order detail shows an orange age-check banner (serves pickup counter and delivery driver), kitchen card + order cards show the badge. Admin editor: alcohol type picker.
- Optional customer accounts (`/app/backend/auth.py`, JWT 30 days, Argon2 via pwdlib, phone = login id, normalised to 0XXXXXXXXX): register/login/profile/saved addresses/order history at `/account` (+ `/account/address` modal). Checkout prefills details, offers saved-address chips and "save this address". Orders store `user_id` (null = guest); guest checkout unchanged. Orders tab merges device orders + account history. Staff lookup `/staff/customers` (GET `/api/customers/search?phone=`) finds accounts and guest orders by phone digits.
- Product photos (`/app/backend/photos.py`): `POST /api/uploads/product-photo` (multipart) -> Pillow optimisation (EXIF fix, max 1600px, progressive JPEG q86) -> Emergent Object Storage (`hallo-magic-pizza/products/<uuid>.jpg`) -> public `GET /api/files/{path}` with disk cache. Product fields `image_url` (main) + `images[]` (additional). Admin PhotoManager: add/replace/remove main, add multiple extras, set-as-main, preview before Save; permission flow with Open Settings. `imgUri()` resolves API-relative urls on web & native. Placeholders (Unsplash) remain until real photos are uploaded.
- Tests: `/app/backend/tests/test_iter5_accounts_alcohol_photos.py` (21, run with `-n 0`).

## Implemented (2026-06) – homepage hero redesign + phone orders (2 iPads)
- Homepage hero: light premium card (brand title, "PIZZERIA · MARLY" kicker, neutral sub text, "Commander maintenant", round real-food photo = Quattro Formaggi main image from the shared catalog). All wood-fired-oven / "feu de bois" / "Holzofen" claims removed. Hero is ~half the previous height so Retrait/Livraison + categories + first products are visible quickly. Upload the real Quattro Formaggi photo via admin → it becomes the hero photo automatically.
- `/phone-orders` (staff PIN gate, link from dashboard header "phone" icon): station picker Poste 1 / Poste 2 saved on device (`phone_station`), big phone-number search (`/api/customers/search`), existing customer card with saved-address chips + per-order address edit + "save to customer"; quick new-customer form (`POST /api/customers`, same `users` collection, password-less until the customer registers – register then claims the record); guest-order details offered as prefill. Menu panel: search + categories + one-tap add (simple products) / product sheet for pizzas (size, dough, extras, removals, note, qty); cart pane with steppers/edit/remove, RETRAIT/LIVRAISON, ASAP or exact time (slots + input), payment Espèces / Terminal / Paiement au retrait|livraison, recap, "CONFIRMER COMMANDE TÉLÉPHONIQUE". Phone/tablet: 2 columns ≥900px, pane switch below.
- `POST /api/phone-orders`: shared `compute_order()` (same prices, VAT snapshot, age_required), created directly as `accepted` with estimated_ready_at (exact time or +30 min), `source=telephone`, `station`, `payment_method`, one kitchen print job (same duplicate guard/reprint), same ticket (adds "TELEPHONE - POSTE n", payment label, driver) and same fiscal receipt. Dashboard badge "TÉLÉPHONE · POSTE n". `POST /api/orders/{id}/assign {driver}` → Livreur 1/2/3 buttons in staff detail for delivery orders (status → assigned when ready).
- Tests: `/app/backend/tests/test_phone_orders_iter6.py` (17, `-n 0`); frontend E2E iteration 6 passed.

## Implemented (2026-06) – operational build: security, drivers, closing, ticket, PrintNode hardening
- Staff auth server-side (`/app/backend/staff_auth.py`): PINs stored as Argon2 hashes in `staff_auth`, `POST /api/auth/staff/login` → role JWT (manager, kitchen, phone, driver1..3), `require_roles()` guards reports/pins/driver endpoints. Dev default PINs 1234/2345/3456/1111/2222/3333 (seeded once; manager changes them in Admin → Sécurité `/staff/admin/security`). Frontend `StaffProvider` stores the token (SecureStore), routes by role; drivers → /driver only, phone role → /phone-orders only, admin/closing manager-only. `EXPO_PUBLIC_STAFF_PIN` no longer used.
- Driver system: `POST /orders/{id}/assign` (Livreur 1/2/3, delivery only, 409 if another driver already picked up), `/api/driver/orders` (own orders only), `/pickup`, `/depart` (→ delivering + customer notification "Votre commande est en livraison."), `/delivered`, `/collect` (explicit; never automatic). Timestamps assigned_at / picked_up_at / out_for_delivery_at / delivered_at / ready_at / collected_at + status_history. `/driver` phone screen with map link, À ENCAISSER / TERMINAL block, age warning, `?o=<id>` focus from ticket QR.
- Collection fields on every order: collection_method (cash|terminal|none), amount_due, payment_collected.
- Manager closing `/staff/closing`: per Livreur 1/2/3 daily deliveries, cash/terminal/paid expected, orders list, actual cash/terminal entry with differences, stored in `closings` by date+driver; totals per source (WEB / APP / TÉLÉPHONE · POSTE 1 / 2).
- Operational ticket rewritten (80 mm): big LIVRAISON/RETRAIT, order number, confirmed time, source, LIVREUR block, payment block, products with modifiers, customer/address, timestamps, ESC/POS QR (delivery, internal `/driver?o=<id>` – no customer data) + QR preview in staff ticket screen, footer "Ticket opérationnel – pas un reçu fiscal". Fiscal receipt untouched.
- PrintNode: job id, last_print_error, print_status failed → PRINT FAILED warning + retry (allowed without force), print jobs preserved; still SIMULATED until `PRINTNODE_API_KEY` / `PRINTNODE_PRINTER_ID` are set in backend/.env.
- Concurrency: phone-order `client_request_id` idempotency (partial unique index), stale status updates → 409, double accept → 400, closed order → 409, double print → 409.
- Tests: `/app/backend/tests/test_staff_driver_iter7.py` (29), iter6 (17), VAT (15) all passing; frontend E2E iteration 7 passed.

## Implemented (2026-06) – security hardening of legacy endpoints
- Every staff/admin/driver endpoint now requires a server-side staff JWT + role: manager/kitchen → staff order list (`GET /orders` without `ids`), accept/reject/delay/status/assign/print/receipt/print-jobs; manager/kitchen/phone → ticket; manager/phone → customers search/create/addresses, phone-orders; manager → product/extra/category/settings writes, photo upload, reports, PIN management; drivers → `/driver/*` (own orders only). Customer-facing stays public: `GET /menu`, `/settings`, `POST /orders`, `GET /orders/{id}`, `GET /orders?ids=` (device-stored ids).
- `EXPO_PUBLIC_STAFF_PIN` removed from frontend .env; no PINs / JWT secret / PrintNode keys in frontend or repo (test asserts it).
- Regression suite: `tests/test_security_iter8.py` (401 unauth, 403 wrong role, allowed roles, customer token ≠ staff token, driver isolation, public endpoints, no secrets) + `tests/conftest.py` injects a manager token into the older functional suites. 110 backend tests passing.
- ⚠ Note: `PUT /settings` replaces the whole settings document – always send the full object (admin screen does).

## Implemented (2026-06) – operational refinements (iteration 9)
- Phone orders: no hard delivery minimum for staff (`compute_order(enforce_minimum=False)`), warning "Sous le minimum de livraison habituel" shown; web/app rule unchanged.
- Driver screen: today only (Europe/Zurich day; active first, "Terminées aujourd'hui" section); PRISE EN CHARGE removed – flow Assigned → PARTI / EN LIVRAISON → confirm collection → LIVRÉE (timestamps kept; `/pickup` endpoint still exists for audit but unused).
- Auto-completion: LIVRÉE (driver or staff) and RETIRÉE → status `completed` automatically (`finish_order`, both events in status_history, `completed_at`). Manager "En cours" refreshes by 3 s polling incl. background.
- Driver shift access: `staff_auth.active` per driver position, `PUT /api/auth/staff/drivers/{role}/active` (manager), ACTIF/INACTIF toggles in Admin → Sécurité; inactive → login 403 and existing sessions rejected; driver JWT expires at 03:00 Zurich (end of shift). Login screen shows the server message (e.g. poste INACTIF).
- Tests: `tests/test_refinements_iter9.py` (6) + frontend iteration 9 (5/5).

## Fixed (2026-06) – driver login / redirect
- Cause: on web the staff session is stored per browser (one session per device). With a Manager/Kitchen session already stored, `/driver` redirected non-drivers to `/staff`, and `/staff/login` auto-redirected any unlocked session to its home before a driver PIN could be typed – so driver PINs "ended up" on the dashboard. Livreur 2/3 had also been left INACTIF by a test run (403 shown as generic error).
- Fix: `/driver` with a non-driver session shows a gate "Session active: … → Se connecter comme livreur" (locks the session, opens `/staff/login?switch=1`) – never the dashboard; `/staff/login?switch=1` shows the PIN form even when unlocked (account switch); login screen displays the server reason (e.g. poste INACTIF). Drivers still can't open /staff, /staff/admin or /phone-orders (redirected to /driver); kitchen/manager/phone can't see driver data.

## Iteration 10 (2026-06) – printing root cause + Manager mobile layout
- ROOT CAUSE tickets not printing: `PRINTNODE_API_KEY` is EMPTY in backend/.env (printer ID 74280690 set) → every accepted order was recorded as `simulated`. Accept flow itself is correct (one idempotent job on accept). Needs the user's PrintNode API key in backend/.env, then backend restart; startup then stamps `settings.printing_enabled_at` so everything older can never print.
- Hardening (server.py): `is_historical()` guard now blocks ALL print paths (auto, manual reprint, receipt) for orders created before `printing_enabled_at`; `/print` on a pending order → 409; startup + per-job logging shows whether PrintNode is configured/sent/failed.
- ⚠ Once the real key is set, DO NOT run the backend test suites (they accept fresh orders → real tickets).
- Manager dashboard mobile cleanup (no logic change): header = title + sound + lock, labelled scrollable nav row (Cuisine / Commandes téléphoniques / Clients / Clôture / Admin); full-width segmented filter with counts; "Première livraison" is a collapsible card (collapsed on phones, open on tablets); order cards restructured (number+status, tags, Commandée/Souhaitée/Confirmée cells, customer, items, total + CTA); detail split into labelled sections (Client, Articles, Accepter la commande, Étape suivante, Livreur, Retard, Annuler, Ticket & reçu). All testIDs preserved.
- Tests: `tests/test_iter10_print_hardening.py` (2), frontend iteration 10 (7/7 + tablet), report `/app/test_reports/iteration_10.json`.

## Iteration 11 (2026-06) – driver identity / closing
- Cause of duplicate closing rows: closing grouped by per-order `driver_name` snapshot; orders assigned before named shifts had no name (→ bare "LIVREUR 1"); test runs re-opened slots with Marco/Luca/Test N; the closing record was keyed by slot only and the assign buttons showed slots only.
- Fix (no order/printing flow touched): `assign` stores `driver_name` + `shift_id` snapshot; driver `delivered` re-attributes the order to the performer (current shift name/id); `GET /reports/closing` groups per identity (slot + person), resolves unnamed legacy orders via the shift open at assignment time else "Non identifié", lists the on-duty person (today only), returns `identity_key`, `legacy`, `is_current`; `POST /reports/closing` keyed by (date, driver, driver_name) – legacy slot-only closings still apply when the slot has a single identity. New `GET /auth/staff/drivers` (manager/kitchen/phone, no PIN data) feeds the assignment buttons ("Livreur 1 — Aliou · En service / service fermé"). Closing screen: one card per identity, on-duty highlighted, legacy hint. Nothing historical rewritten.
- Test: `tests/scenario_driver_identity.py` (manual script – inserts accepted test orders directly in Mongo so NOTHING prints; restores Livreur 3 shift + deletes its docs).

## Iteration 12 (2026-06) – printing rule, scheduled orders, manager alerts
- PREMATURE PRINT root cause: `POST /phone-orders` created phone orders directly as ACCEPTED and called `do_print` → ticket at creation (#1379, #1380). Fixed: phone orders are now PENDING like web/app orders (the agreed "in N min" is stored as `requested_time` for one-tap confirmation); no print at creation.
- ONLY initial-ticket trigger: `accept_order` (`POST /orders/{id}/accept`) → `do_print`. Acceptance is an atomic `find_one_and_update({status:"pending"})` claim (double tap / retry / second device → 400). `do_print` also refuses pending orders (409), enforces one job via `print_lock` + `printed`, and never prints orders created before `printing_enabled_at`. Manual `POST /orders/{id}/print` is the only other path (staff button, force reprint).
- Scheduled orders: `OrderIn.requested_date` (YYYY-MM-DD, ≤7 days, future day must use a slot of THAT day – `hours.slots_for_day`); order stores `requested_date` + `scheduled_for` (UTC); `GET /settings/ordering` returns `days[]` (closed days skipped). Checkout: day chips (Aujourd'hui/Demain/weekday) + that day's slots; defaults to the first day with slots when closed. Customer tracker: "Commande reçue · en attente de confirmation" vs "Commande confirmée". Manager: new "Programmées" segment (pending scheduled orders flash the alert/sound like any pending order), black date banner on card + detail ("PROGRAMMÉES · PAS POUR AUJOURD'HUI · vendredi 18.09.2026 · 18:30"). Accept uses the requested day (`parse_local_time(on_date)`, minutes relative to the slot). Ticket: "### *** COMMANDE PROGRAMMEE *** / PAS POUR AUJOURD'HUI / DATE / HEURE ###" block before the usual header.
- Nothing prints on startup/restart/polling/notifications: no code path other than accept/manual print calls `do_print`.
- Tests: `tests/scenario_print_rule.py` (manual, deletes its orders, accept test uses printed=True pre-flag → no PrintNode job).

## Iteration 13 (2026-06) – Manager service mode (UI only)
- Order card carries the two operational taps: pending → `15 | 20 | 30 MIN` (+ "Confirmer HH:MM" when a time was requested, + "Heure exacte" → opens detail) calling the SAME accept mutation (`POST /orders/{id}/accept`, one ticket); accepted delivery → driver buttons with real shift names (`GET /auth/staff/drivers`), one tap = `POST /orders/{id}/assign` (never prints); assigned → "✓ ALIOU — ASSIGNÉ · Livreur 1". Pickup cards never show driver controls. Card shows #, type, source, times, customer, address, items, total + payment.
- Filters: NOUVELLES | EN COURS | PROGRAMMÉES (large, alert highlight), "Terminées · n" as a secondary link. Tablet: list pane 52% so cards + buttons stay wide, detail on the right. Detail keeps Annuler / Retard / Réimprimer / customer info.
- Verified with pre-flagged (printed=True) preview orders → 0 PrintNode jobs; previews removed.

## Backlog
- P0: PrintNode live credentials + real ESC/POS ticket test on Epson TM-T70II; staff PIN protection.
- P1: real push notifications (Emergent push after build), favourites + one-tap reorder for account holders, dedicated driver view (age-check warning already in staff detail), web layout polish for desktop widths, category manager UI, extras per-size pricing.
- P2: opening-hours enforcement at checkout, order history/statistics, courier assignment screen, multi-printer routing, dark mode.

## Next tasks
1. Collect PrintNode API key + printer ID and test a real print.
3. Wire push notifications after first publish/build.

## Iteration 14 (2026-06) – phone-accept investigation + driver cleanup
- Investigation: #1387 (Poste 2) / #1388 (Poste 1) were still PENDING server-side – no `/accept` request ever reached the backend for them. The only acceptance in that window was #1365, a pre-go-live TEST web order → `skipped_historical` (no ticket by design). #1384 (Poste 1, accepted 18:32) DID print → the shared accept path works for phone orders.
- Changes: `Order.legacy` (created before `printing_enabled_at`) computed in `GET /orders`; Manager operational lists (NOUVELLES/EN COURS/PROGRAMMÉES, alert sound) exclude legacy orders → they sit in "Historique" with a "TEST · avant mise en service · pas de ticket" badge, no quick buttons. Quick-accept toast now reports the print outcome (envoyé / ancienne commande / échoué / simulé). `GET /orders` limit 400.
- Driver: `GET /driver/orders` returns only deliveries of the CURRENT identity (driver_name or shift_id match), created after go-live, active first sorted by promised time; driver screen shows active cards + collapsed "Historique · terminées aujourd'hui". Nothing deleted.
- Test data inventory: 1 275 orders created before go-live (16:30:25 UTC 17.09) = development/test data (1 115 still non-terminal); 9 real orders after. Awaiting user approval before any deletion.

## Iteration 15 (2026-06) – final pass: hours, ticket, review e-mail, menu admin, carousel, backup
- Hours: DB had 'tue': '17.00-22' (unparseable → Tuesday closed). Startup migration + `normalize_hours()` on PUT /settings canonicalise "HH:MM-HH:MM, …"; schedule Mon closed / Tue 17-22 / Wed-Sun 11-14 & 17-22 now identical for ASAP, slots, future days, first-delivery, backend validation.
- ASAP: unchanged storage (`requested_time="asap"`, no fake time). Ticket: "DES QUE POSSIBLE" vs "HEURE DEMANDEE HH:MM" + "CONFIRMEE : HH:MM"; scheduled block kept; source line; payment block DEJA PAYE / A ENCAISSER CHF + ESPECES|TERMINAL; size on its own big line; options/supplements indented under the pizza.
- Print idempotency audit (no change needed): atomic pending→accepted claim in accept_order, do_print pending/printed/print_lock/historical guards, single print call-site + manual reprint.
- Google review e-mail: `review_email.py` (Emergent managed e-mail proxy, guardrail gate, FR/DE template, link = {public_url}/api/review/{id}/go → 302 to google_review_url). Background loop every 60 s: completed orders with customer e-mail, created after go-live, completed_at ≤ now − review_delay_minutes, atomic claim `review_status` (sending→sent/failed). Settings: review_enabled, google_review_url, review_delay_minutes, public_url. .env: EMERGENT_EMAIL_KEY, EMAIL_FROM_NAME, EMAIL_DRY_RUN=1 (set to 0 for production sends).
- Menu admin: categories screen (/staff/admin/categories: FR/DE, ▲▼ order, active, new); product editor: ordre d'affichage, mise en avant (Pizza du moment / Créez votre pizza – listed first via GET /menu ranking), visible from/until dates; extras: per-size prices `price_by_size` {32,40,50} used by compute_order + customer product screen (re-priced on size change).
- Homepage carousel: Settings.hero_images (admin Photos d'accueil via PhotoManager); `HeroCarousel` shown only when photos exist.
- Backup: GET /admin/export (manager) → JSON download/share from Settings.

## Iteration 16 (2026-06) – checkout 500 fix + pre-opening ASAP
- Checkout "Erreur": `compute_order` referenced `size` before assignment (introduced with per-size supplement prices) → HTTP 500 for every web order. Fixed (size key resolved before the extras loop). E2E verified (create → list → accept w/ pre-flag → ticket) with 0 real prints.
- ASAP before opening: `hours.ordering_status` returns `asap_pickup / asap_delivery / asap_from`; backend accepts "asap" when an opening exists later today; checkout keeps "Dès que possible · 11:00" enabled with a hint; Manager quick minutes count from opening time when accepted before opening.
- Supplement MAX is per line item (`min(qty, max_quantity)` per pizza) – unchanged. Per-size prices verified in stored order + ticket.

## Iteration 17 – ticket layout final
- build_ticket now emits real ESC/POS sizes: `escpos_big(text, 3)` (3x bold centered) for LIVRAISON/RETRAIT, order #, requested/confirmed times, amount; `escpos_big(text, 2)` for labels (DES QUE POSSIBLE, HEURE DEMANDEE, CONFIRMEE, DEJA PAYE / A ENCAISSER / ESPECES|TERMINAL, driver, pizza sizes). No blank lines at the top. `strip_escpos()` for app previews / accept response. QR unchanged (delivery only). Print trigger/idempotency untouched. Verified with synthetic dicts only – 0 print jobs.

## Iteration 18 – kitchen ticket FINAL layout
- W=42 (TM-T70 font A). LIVRAISON = 4x bold white-on-black band between # lines; RETRAIT = 4x bold between * lines. Order # 2x. Timing: ASAP → 2x "DES QUE POSSIBLE" + 2x "CONFIRMEE" + 4x time; requested → 2x "LIVRAISON|RETRAIT HH:MM" (+ "CONFIRMEE HH:MM" if changed) + 4x time; scheduled block 2x + 4x time. Items: `escpos_item` = "1x 50 CM" at 2x + name double-height on one line; supplements/options normal indented. Payment/driver double-height. Driver QR + URL removed from the printed ticket and from send_to_printer (escpos_qr unused). Code page: ESC t 16 (WPC1252) + cp1252 encoding → accents OK. No logic changes, 0 print jobs.

## Iteration 19 – ticket time block (delivery label = "LIVRAISON DEMANDÉE", pickup = "RETRAIT À") + item line + same-day "X MIN" accept
- Time block (build_ticket): requested == confirmed → 2x "LIVRAISON À|RETRAIT À" + 4x time (no CONFIRMÉE line); requested != confirmed → 2x "DEMANDÉE HH:MM" + 2x "CONFIRMÉE HH:MM" + 4x confirmed; ASAP → 2x "DÈS QUE POSSIBLE" + 4x confirmed. 4x time is always estimated_ready_at (never accepted_at). Future-day block uses the same DEMANDÉE/CONFIRMÉE or "… À" lines.
- Items: `escpos_item` now prints the whole "1x 50 CM FORESTIÈRE" bold at 2x on one line when ≤ 21 cols, else "1x 50 CM" then the name on the next 2x line. Items without size use the same style.
- Root cause of #1401 (13:45 requested, 12:42 printed): "30 MIN" quick-accept on a SAME-DAY scheduled order counted from now. accept_order now uses the requested slot as base for same-day requested times too (23:45 + 30 → 00:15). Print trigger/idempotency untouched.
- ⚠️ WARNING: running the legacy pytest suites (test_phone_orders_iter6, test_iter10_print_hardening, test_final_iter10 …) with live PRINTNODE keys DISPATCHED 8 REAL TICKETS to the kitchen printer (orders 1413–1457, all deleted afterwards + print_jobs). NEVER run the full test suite while PrintNode keys are in .env; only `scenario_print_rule.py` is safe (it guards real prints). Verify ticket logic with in-process calls and `server.PRINTNODE_API_KEY = ''`.

## Iteration 20 – FINAL POLISH (done, testing agent iter 11: 8/8 backend, all UI checks pass)
- PrintNode key RESTORED after testing (live again). All TEST_ orders created during testing were deleted.
- Dashboard: tabs kept, detail pane removed; responsive grid (1/2/3 cols) of large OrderCards with all actions inline (accept 15/20/30/confirm, next-step status buttons, driver assign/change, Détails modal for delay/cancel/print). Sound: web autoplay unlock banner ("Activer le son") + repeat every 20 s while NOUVELLES > 0.
- Menu: category "Entrées/Vorspeisen" (sort 1) added by seed migration; virtual "Pizza sans gluten" category deleted (gluten_free dough option kept per pizza). DELETE /api/categories/{id} (only if empty). Customer grid 1/2/3 cols, max width 1120, Pizza du mois badge (highlight="moment"), i18n "Pizza du mois"/"Monatspizza".
- Admin: product editor has explicit "Option sans gluten" (price + sizes) and "Option sans lactose" switches replacing the generic pizza-options toggle; extras + categories have delete buttons.
- Ticket item line: ≤21 chars → 2×; ≤42 chars → double-height bold single line ("1x 50 CM QUATTRO FORMAGGI"); longer → head 2× + name double-height line.
- Alert banner timer fixed (was reset by each 3 s poll). Sound verified on web via HTMLMediaElement.play monkeypatch (resolved, ended=true) and on a real new order (2 plays).
- DB still holds ~340 dev orders with customer "TEST*" (hidden from live lists) + other dev orders in Historique – ask user before wiping order history for go-live.
- Production checklist: EMAIL_DRY_RUN=1 in backend/.env (set 0 to send review emails), settings.google_review_url + public_url empty, review_enabled False, phone '026 000 00 00' placeholder, default PINs (1234/2345/3456/1111…) must be changed in Admin → Sécurité.
- Regression fix: nav row (Cuisine / Téléphone / Clients / Clôture / Administration) was inside the header on ≥900 px and got clipped (Administration hidden on 1024 px laptops). Now always a full-width WRAPPING row; Administration button dark-highlighted. Verified all 5 entries fully visible at 1024/768/390 and /staff/admin opens (products, categories, extras, settings, security untouched).

## Iteration 21 – phone orders print immediately (user decision)
- POST /api/phone-orders now inserts the order then calls accept_order() in-process with the agreed time (exact HH:MM → time; ASAP → minutes from Poste chips 15/20/30/45/60, default 30). Order goes straight to EN COURS, exactly ONE kitchen ticket via the same do_print idempotency; header TELEPHONE - POSTE 1/2 unchanged; Manager can still cancel from Détails. client_request_id double tap still returns the same order (no 2nd print).
- Poste panel: minute chips in ASAP mode; success sheet shows confirmed time + print status. Verified simulated (key temporarily removed, then restored): 1 print job per order, correct ticket header. Test orders deleted.
- Real phone orders #1464/#1465 (created before the change) are still PENDING in NOUVELLES – Manager must accept them once.

## Iteration 22 – test-data cleanup + Clôture verification (testing agent iter 12: all PASS, read-only)
- Deleted: 610 automated test orders (TEST*/Test/Demo/Regression/Sec/NoKey/H/P/G/Anna-pytest) + 401 print jobs, 229 TEST_ users, 84 closed "Test*" driver shifts. Kept 46 manual orders by the team (berisha/Berisha/Ema/Fisnik/Sarah/Aliou/Simo/Mohamed/David/Jean/…): uncertain → reported.
- Left untouched (reported): #1387 (cancelled) & #1388 (completed) on 2026-09-17 assigned to dev driver identity "Test" (Livreur 3); pending phone orders #1464/#1465.
- Clôture: livraisons = delivered/completed only; commandes list = all assigned that day; money over delivered only – math verified 0 mismatches. Label now "N commandes · M livraisons · K en cours · C annulées".
- Production URLs: <domain>/ customer · /staff/login (PIN → Manager|Cuisine) · /phone-orders (PIN Téléphone or Manager, Poste chosen on device) · /staff/login → /driver (Livreur PINs from Admin → Sécurité).

## Iteration 23 – FINAL DEV PASS (DONE; PrintNode key restored; testing agent iter 13+14 pass; entrees.name.de fixed to Vorspeisen)
- Sound: shared provider src/staff-sound.tsx mounted in app/staff/_layout.tsx (manager/kitchen): one player, module-level session unlock (no re-unlock when navigating sections), soundOn persisted (AsyncStorage), rings on genuinely new pending order + every 20 s while NOUVELLES non-empty, stops on accept/mute. New louder 2.6 s chime assets/sounds/new-order.wav. Verified in browser: plays at +3 s, +23 s, +43 s, none after accept.
- Card quick accept: 15/20/30/45/60 MIN one tap (locks instantly via `busy`), "AUTRE / HEURE EXACTE · REFUSER" opens detail.
- Checkout: payment choice ESPÈCES / CARTE (TERMINAL) for both types → payment_method cash|terminal (OrderIn.payment_method, default cash); email REQUIRED + validated (frontend + backend 400) for web/app orders only (phone orders unaffected).
- Menu: categories Entrées(1) Salades(2) Pizzas(3) Créer votre pizza(hidden tab, merged inside Pizzas after Pizza du mois) Piadina & Pasta Desserts Boissons. Only one product may be highlight=moment (backend enforces). Admin hint under highlight chip.
- Public: "Accès restaurant" + "Version test" removed from Plus tab; LegalFooter (Confidentialité/CGV/Mentions légales → /legal/[kind]) on home + Plus; texts from settings.legal_privacy/terms/imprint (Admin → Réglages → Textes légaux), placeholder when empty.
- Supplements per line: verified in real cart (3× Margherita each with 2× Jambon) + backend compute – no change needed.
- Verified in browser: mute stops the 20 s repeat, unmute resumes; CONFIRMER 19:30 accept keeps requested time; Poste 2 UI minute chips; admin legal fields. Driver quick-assign requires an OPEN shift (buttons show "service fermé" otherwise – existing behaviour).
- DEVELOPMENT FINISHED. Remaining = restaurant content/config (see final report in chat).
- Ticket FINAL (iter 24): order number "#1474" (2×) now ABOVE the LIVRAISON/RETRAIT band; payment on one bold double-height line "À ENCAISSER · TERMINAL|ESPÈCES · CHF 36.00" (DEJA PAYE unchanged). Verified in-process only, cp1252 OK, no print sent.
- Iter 25 (4 final customer changes, testing agent iter 15 PASS): gluten-free option disabled (no auto size switch) outside 32 cm with hint "Disponible uniquement en 32 cm"/"Nur in 32 cm erhältlich"; size guide 👤/👥/👥👥 on keys 32/40/50 only; Pizza du mois ordering re-verified; DE weekday names in checkout day chips (WEEKDAYS in checkout.tsx). No backend change, no print sent.
