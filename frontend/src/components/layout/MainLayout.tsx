import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import styles from './MainLayout.module.css';

export const MainLayout: React.FC = () => {
  return (
    <div className={styles.layout}>
      <Navbar />
      <main className={styles.main}>
        <Outlet />
      </main>
      <footer className={styles.footer}>
        <div className={`container ${styles.footerContent}`}>
          <p className={styles.tagline}>
            <strong>Mira</strong> — Turn your plans into progress.
          </p>
          <p className={styles.subtext}>
            AI doesn&apos;t decide what you should learn. It helps you actually finish what you&apos;ve decided to learn.
          </p>
        </div>
      </footer>
    </div>
  );
};
