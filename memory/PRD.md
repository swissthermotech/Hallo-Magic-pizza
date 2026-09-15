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

## Backlog
- P0: PrintNode live credentials + real ESC/POS ticket test on Epson TM-T70II; staff PIN protection.
- P1: real push notifications (Emergent push after build), customer accounts (saved address, history, reorder, favourites), web layout polish for desktop widths, photo upload via object storage instead of URL, category manager UI, extras per-size pricing.
- P2: opening-hours enforcement at checkout, order history/statistics, courier assignment screen, multi-printer routing, dark mode.

## Next tasks
1. Collect PrintNode API key + printer ID and test a real print.
2. Add staff PIN and hide staff links from customers.
3. Wire push notifications after first publish/build.
