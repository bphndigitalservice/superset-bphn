import logging

logger = logging.getLogger(__name__)

def sync_public_role_permissions(app) -> None:
    """Copy all permissions from Gamma to Public, plus Theme read access."""
    with app.app_context():
        from superset import security_manager
        try:
            public_role = security_manager.find_role("Public")
            gamma_role = security_manager.find_role("Gamma")
            
            if not public_role:
                logger.warning("Public role not found, skipping sync.")
                return
            if not gamma_role:
                logger.warning("Gamma role not found, skipping sync.")
                return

            # Clean up existing menu_access permissions from Public role
            # so anonymous users don't see the top navigation bars (List Dashboards, etc).
            perms_to_remove = []
            for perm in public_role.permissions:
                if perm.permission.name == "menu_access" and perm.view_menu.name != "Home":
                    perms_to_remove.append(perm)
                    
            for perm in perms_to_remove:
                security_manager.del_permission_role(public_role, perm)
                logger.info("Removed menu_access on %s from Public role", perm.view_menu.name)

            # Copy permissions from Gamma, explicitly excluding menu_access
            for perm in gamma_role.permissions:
                if perm.permission.name == "menu_access":
                    continue
                if perm not in public_role.permissions:
                    security_manager.add_permission_role(public_role, perm)
                    logger.info("Copied Gamma permission %s on %s to Public", perm.permission.name, perm.view_menu.name)

            # Also ensure Theme access (needed for Superset 6 public themes)
            theme_perm = security_manager.find_permission_view_menu("can_read", "Theme")
            if theme_perm and theme_perm not in public_role.permissions:
                security_manager.add_permission_role(public_role, theme_perm)
                logger.info("Granted can_read on Theme to Public role")
                
        except Exception as exc:
            logger.error("Failed to sync Public role permissions: %s", exc)

def auto_grant_public_to_default_dashboard(app) -> None:
    """Automatically grant the Public role access to the default dashboard."""
    import os
    with app.app_context():
        from superset.extensions import db
        from superset.models.dashboard import Dashboard
        from superset import security_manager
        
        slug = os.getenv("SUPERSET_DEFAULT_DASHBOARD_SLUG", "").strip()
        if not slug:
            return
            
        try:
            dashboard = db.session.query(Dashboard).filter(Dashboard.slug == slug).one_or_none()
            if not dashboard:
                logger.warning("Default dashboard %s not found for auto-grant", slug)
                return
                
            public_role = security_manager.find_role("Public")
            if not public_role:
                return

            if public_role not in dashboard.roles:
                dashboard.roles.append(public_role)
                db.session.commit()
                logger.info("Auto-granted Public role access to default dashboard: %s", slug)
        except Exception as exc:
            logger.error("Failed to auto-grant Public role to dashboard: %s", exc)
