import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import styles from '../components/common/Toast.module.css';

export type ToastType = 'success' | 'error' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  subtext?: string;
}

export interface ToastOptions {
  type?: ToastType;
  message: string;
  subtext?: string;
  duration?: number;
}

export interface ToastContextValue {
  showToast: (options: ToastOptions) => void;
  success: (message: string, subtext?: string, duration?: number) => void;
  error: (message: string, subtext?: string, duration?: number) => void;
  info: (message: string, subtext?: string, duration?: number) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    ({ type = 'info', message, subtext, duration = 3500 }: ToastOptions) => {
      const id = `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const newToast: ToastItem = { id, type, message, subtext };

      setToasts((prev) => [...prev.slice(-4), newToast]); // keep at most 5 toasts

      if (duration > 0) {
        setTimeout(() => {
          dismissToast(id);
        }, duration);
      }
    },
    [dismissToast]
  );

  const success = useCallback(
    (message: string, subtext?: string, duration = 3500) => {
      showToast({ type: 'success', message, subtext, duration });
    },
    [showToast]
  );

  const error = useCallback(
    (message: string, subtext?: string, duration = 5000) => {
      showToast({ type: 'error', message, subtext, duration });
    },
    [showToast]
  );

  const info = useCallback(
    (message: string, subtext?: string, duration = 3500) => {
      showToast({ type: 'info', message, subtext, duration });
    },
    [showToast]
  );

  const contextValue = useMemo(
    () => ({ showToast, success, error, info, dismissToast }),
    [showToast, success, error, info, dismissToast]
  );

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      {toasts.length > 0 && (
        <aside
          className={styles.toastContainer}
          role="region"
          aria-label="Notifications"
        >
          {toasts.map((t) => {
            const isError = t.type === 'error';
            return (
              <div
                key={t.id}
                className={`${styles.toast} ${
                  t.type === 'success'
                    ? styles.toastSuccess
                    : isError
                    ? styles.toastError
                    : styles.toastInfo
                }`}
                role={isError ? 'alert' : 'status'}
                aria-live={isError ? 'assertive' : 'polite'}
              >
                <div className={styles.toastIconWrapper}>
                  {t.type === 'success' && <CheckCircle2 size={18} className={styles.iconSuccess} />}
                  {isError && <AlertCircle size={18} className={styles.iconError} />}
                  {t.type === 'info' && <Info size={18} className={styles.iconInfo} />}
                </div>

                <div className={styles.toastContent}>
                  <div className={styles.toastMessage}>{t.message}</div>
                  {t.subtext && <div className={styles.toastSubtext}>{t.subtext}</div>}
                </div>

                <button
                  type="button"
                  className={styles.dismissButton}
                  onClick={() => dismissToast(t.id)}
                  aria-label="Dismiss notification"
                >
                  <X size={14} />
                </button>
              </div>
            );
          })}
        </aside>
      )}
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextValue => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
