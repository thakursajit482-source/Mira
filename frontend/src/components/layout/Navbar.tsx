import React, { useState } from 'react';
import { NavLink, Link } from 'react-router-dom';
import { Compass, Map, PlusCircle, Settings as SettingsIcon, Menu, X } from 'lucide-react';
import styles from './Navbar.module.css';

export const Navbar: React.FC = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen((prev) => !prev);
  };

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false);
  };

  return (
    <header className={styles.header}>
      <div className={`container ${styles.navContainer}`}>
        {/* Brand Logo */}
        <Link to="/" className={styles.brand} onClick={closeMobileMenu}>
          <div className={styles.logoIcon}>
            <span className={styles.logoDot} />
          </div>
          <div className={styles.brandText}>
            <span className={styles.brandName}>Mira</span>
            <span className={styles.brandTagline}>Plans into Progress</span>
          </div>
        </Link>

        {/* Desktop Navigation */}
        <nav className={styles.desktopNav} aria-label="Main Navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `${styles.navLink} ${isActive ? styles.activeLink : ''}`
            }
          >
            <Compass size={18} />
            <span>Today</span>
          </NavLink>

          <NavLink
            to="/roadmap"
            className={({ isActive }) =>
              `${styles.navLink} ${isActive ? styles.activeLink : ''}`
            }
          >
            <Map size={18} />
            <span>Roadmap</span>
          </NavLink>

          <NavLink
            to="/create"
            className={({ isActive }) =>
              `${styles.navLink} ${isActive ? styles.activeLink : ''}`
            }
          >
            <PlusCircle size={18} />
            <span>Create</span>
          </NavLink>

          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `${styles.navLink} ${isActive ? styles.activeLink : ''}`
            }
          >
            <SettingsIcon size={18} />
            <span>Settings</span>
          </NavLink>
        </nav>

        {/* Mobile Menu Toggle Button */}
        <button
          className={styles.mobileToggle}
          onClick={toggleMobileMenu}
          aria-label={isMobileMenuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={isMobileMenuOpen}
        >
          {isMobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {/* Mobile Drawer */}
      {isMobileMenuOpen && (
        <div className={styles.mobileMenu}>
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `${styles.mobileNavLink} ${isActive ? styles.mobileActiveLink : ''}`
            }
            onClick={closeMobileMenu}
          >
            <Compass size={20} />
            <span>Today</span>
          </NavLink>

          <NavLink
            to="/roadmap"
            className={({ isActive }) =>
              `${styles.mobileNavLink} ${isActive ? styles.mobileActiveLink : ''}`
            }
            onClick={closeMobileMenu}
          >
            <Map size={20} />
            <span>Roadmap</span>
          </NavLink>

          <NavLink
            to="/create"
            className={({ isActive }) =>
              `${styles.mobileNavLink} ${isActive ? styles.mobileActiveLink : ''}`
            }
            onClick={closeMobileMenu}
          >
            <PlusCircle size={20} />
            <span>Create Roadmap</span>
          </NavLink>

          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `${styles.mobileNavLink} ${isActive ? styles.mobileActiveLink : ''}`
            }
            onClick={closeMobileMenu}
          >
            <SettingsIcon size={20} />
            <span>Settings</span>
          </NavLink>
        </div>
      )}
    </header>
  );
};
