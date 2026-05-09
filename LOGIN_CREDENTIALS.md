AERO LOGIN CREDENTIALS REFERENCE
=================================

Application URL: http://localhost:8502

===================================================================
TEST USER ACCOUNTS (For Development & Testing)
===================================================================

USER #1 - FULL ACCESS (Operations)
─────────────────────────────────
User ID:     admin
Password:    Admin@123456
Role:        Operations
Display:     Administrator
Access:      All features, all sections, admin panel

Test Flow:
1. Home page (complete overview)
2. Facilities → Station planning
3. Facilities → Hub planning  
4. Gateway → Gateway operations
5. Services → Services operations
6. Analytics → Executive dashboard
7. Admin → Configuration panel


USER #2 - FACILITY PLANNER
──────────────────────────
User ID:     facility_mgr
Password:    Facility@2024
Role:        Facility
Display:     Facility Manager
Access:      Station & Hub planning, Area configuration

Test Flow:
1. Home page
2. Facilities → Station planner
3. Facilities → Hub planner
4. Admin → Configuration (area parameters)


USER #3 - GATEWAY COORDINATOR
─────────────────────────────
User ID:     gateway_coord
Password:    Gateway@2024
Role:        Gateway
Display:     Gateway Coordinator
Access:      Gateway operations only

Test Flow:
1. Home page
2. Gateway → Gateway operations


USER #4 - SERVICES OPERATIONS
─────────────────────────────
User ID:     services_lead
Password:    Services@2024
Role:        Services
Display:     Services Lead
Access:      Services operations only

Test Flow:
1. Home page
2. Services → Services operations


USER #5 - EXECUTIVE/LEADERSHIP
──────────────────────────────
User ID:     executive
Password:    Leadership@2024
Role:        Leadership
Display:     Executive Lead
Access:      Executive dashboards and analytics

Test Flow:
1. Home page
2. Leadership → Executive dashboard


===================================================================
ROLE CAPABILITIES MATRIX
===================================================================

Feature                    │ Facility │ Gateway │ Services │ Leadership │ Operations
────────────────────────────────────────────────────────────────────────────────────
Home Page                  │    ✓     │    ✓    │    ✓     │     ✓      │     ✓
Station Planning           │    ✓     │    ✗    │    ✗     │     ✗      │     ✓
Hub Planning               │    ✓     │    ✗    │    ✗     │     ✗      │     ✓
Area Planning              │    ✓     │    ✗    │    ✗     │     ✗      │     ✓
Courier Planning           │    ✓     │    ✗    │    ✗     │     ✗      │     ✓
Resource Planning          │    ✓     │    ✗    │    ✗     │     ✗      │     ✓
Health Monitor             │    ✓     │    ✗    │    ✗     │     ✗      │     ✓
Gateway Operations         │    ✗     │    ✓    │    ✗     │     ✗      │     ✓
Services Operations        │    ✗     │    ✗    │    ✓     │     ✗      │     ✓
Executive Dashboard        │    ✗     │    ✗    │    ✗     │     ✓      │     ✓
Admin Configuration        │    ✗     │    ✗    │    ✗     │     ✗      │     ✓


===================================================================
TROUBLESHOOTING LOGIN ISSUES
===================================================================

Q: Login fails with "Invalid credentials"
A: 
   1. Check spelling of User ID (case-insensitive, but exact)
   2. Verify password is correct
   3. Ensure AERO_USERS.xlsx file exists in data/ directory
   4. Try admin account first to verify system is working

Q: "Access denied. You do not have permission to view this page"
A:
   1. You are logged in but don't have permission for that page
   2. Check your role and the role requirements for that page
   3. Try the admin account which has access to everything

Q: Can't log out properly
A:
   1. Use the "SIGN OUT" button in the left sidebar
   2. Browser cache may need clearing
   3. Try incognito/private browsing mode

Q: Session times out
A:
   1. Sessions may expire after inactivity
   2. Log back in with your credentials
   3. Check Streamlit config for session timeout settings


===================================================================
TESTING CHECKLIST
===================================================================

□ Test Login
  □ admin → Login succeeds → Home page shows
  □ Invalid password → Error message appears
  □ Invalid user ID → Error message appears

□ Test Role-Based Access
  □ facility_mgr → Can access Facilities section
  □ facility_mgr → Cannot access Gateway section
  □ gateway_coord → Can only see Gateway operations
  □ executive → Can access Analytics

□ Test Navigation
  □ Navigation menu updates based on role
  □ Can navigate between allowed pages
  □ Cannot navigate to restricted pages

□ Test Sign Out
  □ Sign out button works
  □ Redirects to login page
  □ Can log back in

□ Test Data Persistence
  □ Changes save to AERO_USERS.xlsx
  □ User list in admin panel shows all 5 users
  □ User properties match definitions


===================================================================
PASSWORD SECURITY NOTES
===================================================================

✓ Passwords are hashed using bcrypt (SHA-2, work factor 12)
✓ Plaintext passwords are never logged or displayed
✓ Passwords never stored in application logs
✓ Legacy SHA-256 hashes automatically upgrade to bcrypt on login
✓ Each password has a unique salt (per-user security)

For production:
- Change all test passwords before deploying
- Use strong passwords (12+ characters, mixed case, numbers, symbols)
- Rotate passwords every 90 days
- Never share passwords in email or chat
- Use single sign-on (SSO) if available


===================================================================
ADDING NEW USERS
===================================================================

To add more users:

1. Edit the .env file in the project root
2. Add new AERO_SEED_USER_N entries:

   AERO_SEED_USER_6_ID=john_planner
   AERO_SEED_USER_6_PASS=SecurePass123!
   AERO_SEED_USER_6_ROLE=Facility
   AERO_SEED_USER_6_NAME=John Planner

3. Run the setup script:
   $ python setup_users.py

4. New users will be added to AERO_USERS.xlsx
5. Restart the application

Valid Role Values:
- Facility (facility planning access)
- Gateway (gateway operations)
- Services (services operations)
- Leadership (executive dashboards)
- Operations (full access)


===================================================================
FILE LOCATIONS
===================================================================

User Credentials:   data/AERO_USERS.xlsx
Environment Config: .env (project root)
Setup Script:       setup_users.py (project root)
Application:        main.py (project root)


===================================================================
SUPPORT CONTACTS
===================================================================

For login issues:
- Check .env file exists and has correct variables
- Verify AERO_USERS.xlsx is readable
- Check application logs in terminal

For application issues:
- Review SETUP_COMPLETE.md for troubleshooting
- Check aero/auth/service.py for auth logic
- Review pages/* files for page-specific code

For database issues:
- See SETUP_COMPLETE.md PostgreSQL section
- Check aero/data/postgres.py for connection logic
- Verify PostgreSQL is running if using database features


===================================================================

Last Updated: 2026-05-04
Status: Ready for Testing ✓

