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
