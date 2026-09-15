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

## Backlog
- P0: PrintNode live credentials + real ESC/POS ticket test on Epson TM-T70II; staff PIN protection.
- P1: real push notifications (Emergent push after build), favourites + one-tap reorder for account holders, dedicated driver view (age-check warning already in staff detail), web layout polish for desktop widths, category manager UI, extras per-size pricing.
- P2: opening-hours enforcement at checkout, order history/statistics, courier assignment screen, multi-printer routing, dark mode.

## Next tasks
1. Collect PrintNode API key + printer ID and test a real print.
3. Wire push notifications after first publish/build.
