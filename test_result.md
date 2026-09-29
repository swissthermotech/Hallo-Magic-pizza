#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================
## Iteration 20 (final polish) – main agent notes for testing agent
- PRINTING IS SIMULATED (PRINTNODE_API_KEY temporarily removed) – accepting orders is safe. Still: create as FEW test orders as possible, customer first_name must start with "TEST_" so they can be deleted afterwards.
- Do NOT run backend pytest suites in /app/backend/tests.
- Manager PIN 1234 at /staff/login. Dashboard /staff: tabs NOUVELLES / EN COURS / PROGRAMMÉES / HISTORIQUE, cards with inline actions, "Activer le son" banner (web autoplay unlock), Détails modal.
- Admin: /staff/admin → categories (delete only when empty), products (editor: Option sans gluten/sans lactose switches), extras (delete button in editor), Pizza du mois highlight chip.
- Customer: category chips Tout / Entrées / Pizza / Créer votre pizza / Piadina & Pasta / Dessert / Boissons (NO "Pizza sans gluten"). Gluten-free = dough option inside pizza detail (+CHF 4, 32 cm only).

## Iteration 21/22 – phone-order auto-print + data cleanup + Clôture check (main agent notes)
- PRINTNODE IS LIVE. Do NOT create orders via POST /api/phone-orders (prints immediately) unless the key is disabled. For any order creation test, main agent must disable the key first (currently LIVE – testing agent must NOT create/accept orders; READ-ONLY verification of Clôture only).
- Cleanup done: 610 automated test orders, 229 TEST_ users, 84 closed "Test*" driver shifts deleted. 46 orders remain (manual test orders by the restaurant team).
- Clôture livreurs: GET /api/reports/closing?date=YYYY-MM-DD (manager). Semantics: "livraisons" = orders with status delivered/completed assigned to that driver identity that day; "commandes" list = ALL orders assigned that day (incl. en cours / annulées). Money totals only over delivered/completed.

## Iteration 23 notes for testing agent
- Printing SIMULATED right now (key disabled). Test customers must use first_name "TEST_..." and email like test@example.com; delete them at the end (Mongo orders collection).
- New: checkout requires email + payment choice (testIDs checkout-email, checkout-pay-cash, checkout-pay-terminal). Quick accept testIDs staff-quick-{15,20,30,45,60}-<id>, staff-quick-other-<id>. Sound banner testID staff-sound-enable, toggle staff-sound-toggle, alert new-order-alert. Legal: legal-footer, legal-link-{privacy,terms,imprint}, legal-body-*. Admin settings: settings-legal_privacy-fr etc.

## Iteration 27 – Admin CRUD/upload pass + customer database + marketing consent (main agent notes for testing agent)
- PRINTING SIMULATED during this test round (PRINTNODE_API_KEY renamed in backend/.env; main agent restores it afterwards). Still: do NOT run backend pytest suites; do NOT accept orders unless needed; test customers must use first_name "TEST_" + email test@example.com; test products/supplements must be named "ZZTEST ..." – all deleted by main agent afterwards.
- Manager PIN 1234 (/staff/login). Admin: /staff/admin (products list, ▲▼ ordering inside a category), /staff/admin/product/new (editor), /staff/admin/extras, /staff/customers (NEW customer database), /staff/customers/<key> (NEW profile).
- Product editor testIDs: editor-cat-<slug>, editor-name-fr/de, editor-desc-fr/de, editor-price (optional when sizes exist), editor-sizes (structured rows): editor-size-preset-32/40/50/26, editor-size-add, editor-size-key-<i>, editor-size-label-<i>, editor-size-price-<i>, editor-size-remove-<i>; editor-ingredients; editor-available; editor-customizable; editor-gluten-free; editor-lactose-free; editor-save; editor-delete. Photo: photo-main-pick (file chooser – on web set the input file via Playwright; upload is compressed client-side with expo-image-manipulator then POST /api/uploads/product-photo).
- Extras editor testIDs: extras-new, extra-name-fr/de, extra-price (text, decimals allowed), extra-max, extra-price-32/40/50, extra-available (switch), extra-save, extra-delete, extra-item-<key>. New supplement is auto-added to allowed_extra_ids of all customizable products (backend) and its key is made unique automatically.
- Customers: GET /api/customers?q=&marketing=all|yes|no (manager/phone), GET /api/customers/<key>/profile, PUT /api/customers/<key>/marketing {consent} (manager), GET /api/customers/marketing-export.csv (manager). UI testIDs: customers-search-input, customers-filter-all/yes/no, customers-export-csv, customer-row-<key>, customer-marketing-<key>; profile: customer-profile-card, customer-first-name/last-name/phone/email/kind, customer-orders-count, customer-last-order, customer-total-spent, customer-address-<i>, customer-marketing-status, customer-marketing-switch, customer-order-<id>.
- Marketing consent: checkout testID marketing-consent-checkbox (unchecked by default, optional; text marketing-consent-text FR/DE), account register auth-marketing-checkbox, account profile profile-marketing-switch. Backend: OrderIn.marketing_consent, RegisterIn.marketing_consent, PUT /api/auth/me/marketing; stored in collection marketing_consents keyed by phone digits (consent, at, source checkout|account|staff, history).
- Staff 401 handling: an expired/invalid staff token now locks the session and shows the reason on the PIN screen.

## Iteration 28 – Staff PASSWORD authentication (replaces numeric PIN) – main agent notes for testing agent
- PRINTNODE IS LIVE and EMAIL_DRY_RUN=1. DO NOT create/accept/cancel/print any order, do not touch products/settings/customers. Only the staff authentication flow + read-only rendering of Manager screens is in scope.
- Backend (preview sandbox, /api): POST /auth/staff/login {password} (was {pin}); 401 "Mot de passe incorrect – N tentatives restantes", 5 failures from one client => 429 "Trop de tentatives – accès bloqué pendant 15 min" (collection staff_login_attempts, keyed by sha256 of client IP; clear it in Mongo to unblock). PUT /auth/staff/password {role, password} (manager only, rules: 10–128 chars, letters+digits+special, 400 on weak, 409 duplicate across roles, 400 for driver roles), returns access_token when manager changes its own password. GET /auth/staff/roles -> credential: password|pin|none. Token claim cv = credential_version; changing a password revokes older sessions of that role. Legacy numeric PINs are accepted only while a role has no password_hash.
- Backend scenario already PASSED (26 checks): /app/backend/tests/scenario_staff_password.py (uses local Mongo to clear lockouts). Do not run other pytest suites.
- Sandbox credentials now: Manager `Preview-Manager-2026!`, Kitchen `Preview-Cuisine-2026!`, Phone `Preview-Phone-2026!` (see /app/memory/test_credentials.md). Old PINs 1234/2345/3456 must be REJECTED.
- Frontend: /staff/login testIDs staff-password-input (type=password), staff-password-toggle (eye), staff-pin-submit, staff-pin-error, staff-backend-host. Hidden access unchanged: Plus tab -> long-press ~4 s on testID more-restaurant-name. Admin → Sécurité (/staff/admin/security): security-legacy-warning, security-credential-<role> badge, security-password-<role>, security-confirm-<role>, security-show-<role>, security-save-<role> (disabled until rules + confirmation match). If you change the manager password in the UI, set it back to `Preview-Manager-2026!` at the end.
- Frontend verified by main agent via screenshots: wrong password message, manager login, Admin → Sécurité legacy warning, setting the phone password via UI.

## Iteration 29 – Admin → Sécurité password form: Save button / live rule checklist (sandbox only)
- Bug reported on production web: "Enregistrer" stayed disabled although both fields had a valid password. Fix: Save is now enabled as soon as BOTH fields are non-empty; a live checklist (testID security-checks-<role>) shows each rule ✓/✗ (10 chars, letter, digit, special, no leading/trailing space, both fields identical). On press, the first failing rule is shown in an error toast (client) or the server message (400/409).
- Sandbox creds: Manager `Preview-Manager-2026!` (login at /staff/login; if 429 lock, clear Mongo collection staff_login_attempts). Kitchen currently `Preview-Cuisine-2026!`, Phone `Preview-Phone-2026!`. If you change kitchen/phone in the test, set them back to those values at the end (same screen). Do NOT change the Manager password. No orders/prints/emails.

## Iteration 30 – App Store readiness: in-app customer account deletion (sandbox only)
- New: Account screen (logged-in) → link "Supprimer mon compte" (testID account-delete-open) → modal (account-delete-modal) with password field (account-delete-password), buttons account-delete-cancel / account-delete-confirm (disabled until password typed). Backend DELETE /api/auth/me {password}: 403 wrong password, 409 if an order of this customer is still in progress, 200 {ok, anonymised_orders} -> user deleted, orders anonymised ("Client supprimé", no phone/email/street), stored tickets redacted, old JWT -> 401. Backend scenario passed 16/16 (tests/scenario_account_deletion.py).
- Test with a NEW throwaway account you register in the sandbox (e.g. phone 079 123 45 67 / password Delete-Me-2026!). Do NOT delete the existing sandbox account 079 555 12 34 and do NOT touch production. Do not place orders (PrintNode live) – an account with zero orders can be deleted directly.
- Also changed (config only): camera/microphone/FaceID usage strings removed, usesNonExemptEncryption=false, react-native-webview removed. FR + DE strings added.
