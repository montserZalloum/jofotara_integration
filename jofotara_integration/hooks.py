app_name = "jofotara_integration"
app_title = "Jofotara Integration"
app_publisher = "corex"
app_description = "JoFotara integration"
app_email = "corex@aurevia.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "jofotara_integration",
# 		"logo": "/assets/jofotara_integration/logo.png",
# 		"title": "Jofotara Integration",
# 		"route": "/jofotara_integration",
# 		"has_permission": "jofotara_integration.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/jofotara_integration/css/jofotara_integration.css"
# app_include_js = "/assets/jofotara_integration/js/jofotara_integration.js"

# include js, css files in header of web template
# web_include_css = "/assets/jofotara_integration/css/jofotara_integration.css"
# web_include_js = "/assets/jofotara_integration/js/jofotara_integration.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "jofotara_integration/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Sales Invoice": "public/js/sales_invoice.js",
	"Company": "public/js/company.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "jofotara_integration/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "jofotara_integration.utils.jinja_methods",
# 	"filters": "jofotara_integration.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "jofotara_integration.install.before_install"
after_install = "jofotara_integration.install.after_install"

# Fixtures
# --------
fixtures = ["Print Format"]

# Uninstallation
# ------------

# before_uninstall = "jofotara_integration.uninstall.before_uninstall"
# after_uninstall = "jofotara_integration.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "jofotara_integration.utils.before_app_install"
# after_app_install = "jofotara_integration.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "jofotara_integration.utils.before_app_uninstall"
# after_app_uninstall = "jofotara_integration.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "jofotara_integration.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Company": "jofotara_integration.overrides.company.CompanyOverride"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Sales Invoice": {
		"on_submit": "jofotara_integration.overrides.sales_invoice.on_submit"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"jofotara_integration.tasks.all"
# 	],
# 	"daily": [
# 		"jofotara_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"jofotara_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"jofotara_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"jofotara_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "jofotara_integration.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "jofotara_integration.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "jofotara_integration.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["jofotara_integration.utils.before_request"]
# after_request = ["jofotara_integration.utils.after_request"]

# Job Events
# ----------
# before_job = ["jofotara_integration.utils.before_job"]
# after_job = ["jofotara_integration.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"jofotara_integration.auth.validate"
# ]

# Custom Fields
# -------------
# Custom fields for ERPNext doctypes

custom_fields = {
	"Sales Invoice": [
		{
			"fieldname": "custom_einvoice_status",
			"label": "E-Invoice Status",
			"fieldtype": "Select",
			"options": "Pending\nSubmitted\nAccepted\nRejected",
			"default": "Pending",
			"read_only": 1,
			"insert_after": "status",
			"allow_on_submit": 1,
			"in_list_view": 1,
			"in_standard_filter": 1
		},
		{
			"fieldname": "custom_einvoice_uuid",
			"label": "E-Invoice UUID",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "custom_einvoice_status",
			"allow_on_submit": 1,
			"in_list_view": 0
		},
		{
			"fieldname": "custom_einvoice_qr_code",
			"label": "E-Invoice QR Code",
			"fieldtype": "Long Text",
			"read_only": 1,
			"insert_after": "e_invoice_uuid",
			"allow_on_submit": 1,
			"in_list_view": 0
		},
		{
			"fieldname": "icv_counter",
			"label": "ICV Counter",
			"fieldtype": "Int",
			"read_only": 1,
			"insert_after": "custom_einvoice_qr_code",
			"allow_on_submit": 1,
			"in_list_view": 0
		}
	]
}

after_migrate = [
    "jofotara_integration.custom.company.add_custom_fields",
    "jofotara_integration.install.after_migrate"
]
# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

