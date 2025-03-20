# resource "aws_cognito_user_pool" "user_pool_quotezen" {
#   name = "${var.project_name}_${var.environment}_user_pool"
#
#   # 📜 Configurar la autenticación por correo y contraseña
#   username_attributes      = ["email"]
#   auto_verified_attributes = ["email"]
#
#   password_policy {
#     minimum_length    = 8
#     require_lowercase = true
#     require_uppercase = true
#     require_numbers   = true
#     require_symbols   = false
#   }
#
#   admin_create_user_config {
#     allow_admin_create_user_only = false
#   }
#
#   email_configuration {
#     email_sending_account = "COGNITO_DEFAULT"
#   }
#
#   mfa_configuration = "OFF" # 🔹 Se usa OTP solo para confirmación de cuenta
# }
#
# resource "aws_cognito_user_pool_client" "user_pool_client_quotezen" {
#   name                                 = "${var.project_name}_${var.environment}_client"
#   user_pool_id                         = aws_cognito_user_pool.user_pool_quotezen.id
#   explicit_auth_flows                   = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_PASSWORD_AUTH"]
#   generate_secret                       = false
#   prevent_user_existence_errors         = "ENABLED"
#   allowed_oauth_flows_user_pool_client  = true
#   allowed_oauth_flows                   = ["implicit", "code"]
#   allowed_oauth_scopes                  = ["email", "openid", "profile"]
#   callback_urls                         = ["https://yourfrontend.com/auth/callback"]
#   logout_urls                           = ["https://yourfrontend.com/logout"]
#   supported_identity_providers          = ["COGNITO"]
# }
#
# # Cognito domain configuration
# resource "aws_cognito_user_pool_domain" "cognito_domain_quotezen" {
#   domain       = "${var.project_name}-${var.environment}"
#   user_pool_id = aws_cognito_user_pool.user_pool_quotezen.id
# }