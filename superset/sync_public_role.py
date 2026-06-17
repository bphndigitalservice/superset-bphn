import logging

logger = logging.getLogger(__name__)

def sync_public_role_permissions(app) -> None:
    """Ensure Public role has required permissions for dashboards and themes."""
    with app.app_context():
        from superset import security_manager
        try:
            public_role = security_manager.find_role("Public")
            if not public_role:
                logger.warning("Public role not found, skipping sync.")
                return

            # Core view menus that Gamma has
            view_menus = [
                ("can_read", "Dashboard"),
                ("can_read", "Chart"),
                ("can_read", "Dataset"),
                ("can_dashboard", "Superset"),
                ("can_explore_json", "Superset"),
                ("can_read", "Theme"),       # <--- The crucial fix for Superset 6 themes!
                ("can_read", "CssTemplate"), # Custom CSS might need this
            ]

            for perm_name, view_name in view_menus:
                perm_view = security_manager.find_permission_view_menu(perm_name, view_name)
                if perm_view:
                    if perm_view not in public_role.permissions:
                        security_manager.add_permission_role(public_role, perm_view)
                        logger.info("Granted %s on %s to Public role", perm_name, view_name)
                else:
                    logger.debug("Permission %s on %s does not exist yet.", perm_name, view_name)
                    
        except Exception as exc:
            logger.error("Failed to sync Public role permissions: %s", exc)
