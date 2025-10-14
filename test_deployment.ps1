# Test Multi-User System on Railway Deployment
$baseUrl = "https://llm-search.curam-ai.com.au"

Write-Host "🧪 Testing Multi-User System on Railway" -ForegroundColor Green
Write-Host "Base URL: $baseUrl" -ForegroundColor Yellow
Write-Host "=" * 50

# Test 1: Check if migration page exists
Write-Host "`n📋 Step 1: Testing Migration Page Access"
try {
    $response = Invoke-WebRequest -Uri "$baseUrl/migrate-user-system" -Method GET -ErrorAction Stop
    Write-Host "✅ Migration page accessible (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "❌ Migration page not accessible: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Run Migration (this will create the user system)
Write-Host "`n🚀 Step 2: Running Migration"
try {
    $response = Invoke-WebRequest -Uri "$baseUrl/migrate-user-system" -Method POST -ContentType "application/json" -Body "{}" -ErrorAction Stop
    $result = $response.Content | ConvertFrom-Json
    
    if ($result.success) {
        Write-Host "✅ Migration successful!" -ForegroundColor Green
        Write-Host "   - Conversations updated: $($result.stats.conversations_updated)"
        Write-Host "   - Projects updated: $($result.stats.projects_updated)"
        Write-Host "   - Context items updated: $($result.stats.context_items_updated)"
        Write-Host "   - Admin User ID: $($result.stats.admin_user_id)"
    } else {
        Write-Host "❌ Migration failed: $($result.error)" -ForegroundColor Red
    }
} catch {
    Write-Host "⚠️ Migration may have already been run or error occurred: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Test 3: Try to login with default admin credentials
Write-Host "`n🔐 Step 3: Testing Admin Login"
try {
    $loginData = @{
        username_or_email = "admin"
        password = "admin123"
    } | ConvertTo-Json

    $response = Invoke-WebRequest -Uri "$baseUrl/api/users/login" -Method POST -ContentType "application/json" -Body $loginData -ErrorAction Stop
    $result = $response.Content | ConvertFrom-Json
    
    if ($result.success) {
        Write-Host "✅ Admin login successful!" -ForegroundColor Green
        Write-Host "   - Username: $($result.user.username)"
        Write-Host "   - Role: $($result.user.role)"
        Write-Host "   - Email: $($result.user.email)"
        
        # Store session for further tests
        $sessionToken = $result.session_token
        $headers = @{
            'Content-Type' = 'application/json'
            'Cookie' = "session=$sessionToken"
        }
        
        # Test 4: Get current user profile
        Write-Host "`n👤 Step 4: Testing User Profile"
        try {
            $profileResponse = Invoke-WebRequest -Uri "$baseUrl/api/users/me" -Method GET -Headers $headers -ErrorAction Stop
            $profile = $profileResponse.Content | ConvertFrom-Json
            
            Write-Host "✅ Profile retrieved successfully!" -ForegroundColor Green
            Write-Host "   - Display Name: $($profile.user.display_name)"
            Write-Host "   - Created: $($profile.user.created_at)"
            Write-Host "   - Last Login: $($profile.user.last_login_at)"
        } catch {
            Write-Host "❌ Failed to get profile: $($_.Exception.Message)" -ForegroundColor Red
        }
        
        # Test 5: List users (admin function)
        Write-Host "`n👥 Step 5: Testing User List (Admin)"
        try {
            $usersResponse = Invoke-WebRequest -Uri "$baseUrl/api/users/" -Method GET -Headers $headers -ErrorAction Stop
            $users = $usersResponse.Content | ConvertFrom-Json
            
            Write-Host "✅ User list retrieved successfully!" -ForegroundColor Green
            Write-Host "   - Total users: $($users.users.Count)"
            foreach ($user in $users.users) {
                Write-Host "   - $($user.username) ($($user.role)) - $($user.status)"
            }
        } catch {
            Write-Host "❌ Failed to get user list: $($_.Exception.Message)" -ForegroundColor Red
        }
        
    } else {
        Write-Host "❌ Admin login failed: $($result.error)" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Login request failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 6: Register a new user
Write-Host "`n📝 Step 6: Testing User Registration"
try {
    $newUser = @{
        username = "testuser"
        email = "test@example.com"
        password = "testpass123"
        first_name = "Test"
        last_name = "User"
    } | ConvertTo-Json

    $response = Invoke-WebRequest -Uri "$baseUrl/api/users/register" -Method POST -ContentType "application/json" -Body $newUser -ErrorAction Stop
    $result = $response.Content | ConvertFrom-Json
    
    if ($result.success) {
        Write-Host "✅ New user registered successfully!" -ForegroundColor Green
        Write-Host "   - Username: $($result.user.username)"
        Write-Host "   - Email: $($result.user.email)"
        Write-Host "   - Role: $($result.user.role)"
        Write-Host "   - Email verification required: $($result.email_verification_required)"
    } else {
        Write-Host "❌ User registration failed: $($result.error)" -ForegroundColor Red
    }
} catch {
    Write-Host "⚠️ Registration may have failed (user might already exist): $($_.Exception.Message)" -ForegroundColor Yellow
}

# Test 7: Test new user login
Write-Host "`n🔑 Step 7: Testing New User Login"
try {
    $testLoginData = @{
        username_or_email = "testuser"
        password = "testpass123"
    } | ConvertTo-Json

    $response = Invoke-WebRequest -Uri "$baseUrl/api/users/login" -Method POST -ContentType "application/json" -Body $testLoginData -ErrorAction Stop
    $result = $response.Content | ConvertFrom-Json
    
    if ($result.success) {
        Write-Host "✅ Test user login successful!" -ForegroundColor Green
        Write-Host "   - Username: $($result.user.username)"
        Write-Host "   - Role: $($result.user.role)"
    } else {
        Write-Host "❌ Test user login failed: $($result.error)" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Test user login request failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n📊 Testing Complete!" -ForegroundColor Green
Write-Host "=" * 50

Write-Host "`n🎯 Next Steps:"
Write-Host "1. If migration was successful, change the admin password immediately!"
Write-Host "2. You can now create new users via the API or web interface"
Write-Host "3. Test the role-based permissions with different user types"
Write-Host "4. Integration with your existing chat system should work automatically"

Write-Host "`n🔑 Default Admin Credentials (CHANGE THESE!):"
Write-Host "   Username: admin"
Write-Host "   Password: admin123"
