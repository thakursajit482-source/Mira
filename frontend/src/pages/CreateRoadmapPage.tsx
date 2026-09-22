import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Clock, Calendar, BookOpen, Lightbulb } from 'lucide-react';
import { generateRoadmap } from '../api/roadmaps';
import { DEV_USER } from '../utils/devUser';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { ErrorBanner } from '../components/common/ErrorBanner';
import styles from './CreateRoadmapPage.module.css';

export const CreateRoadmapPage: React.FC = () => {
  const navigate = useNavigate();

  const [goal, setGoal] = useState('');
  const [durationDays, setDurationDays] = useState(14);
  const [dailyMinutes, setDailyMinutes] = useState(DEV_USER.dailyAvailableMinutes);
  const [context, setContext] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!goal.trim()) {
      setError('Please provide a learning goal or objective.');
      return;
    }

    if (durationDays < 1 || durationDays > 365) {
      setError('Target duration must be between 1 and 365 days.');
      return;
    }

    if (dailyMinutes < 15 || dailyMinutes > 720) {
      setError('Daily available time must be between 15 and 720 minutes.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await generateRoadmap({
        user_id: DEV_USER.id,
        goal: goal.trim(),
        target_duration_days: durationDays,
        daily_available_minutes: dailyMinutes,
        context: context.trim() ? context.trim() : null,
      });

      // On successful creation, navigate to the Roadmap view
      navigate('/roadmap');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate roadmap';
      setError(msg);
      setIsLoading(false);
    }
  };

  return (
    <div className="container">
      <div className={styles.wrapper}>
        {/* Page Header */}
        <div className={styles.header}>
          <span className={styles.category}>AI Plan Builder</span>
          <h1 className={styles.title}>Create Your Roadmap</h1>
          <p className={styles.subtitle}>
            Turn what you want to learn into a structured, day-wise level progression tailored to your schedule.
          </p>
        </div>

        {error && <ErrorBanner message={error} onRetry={() => setError(null)} />}

        {/* Main Form Card */}
        <Card padding="lg" className={styles.formCard}>
          <form onSubmit={handleSubmit} className={styles.form}>
            {/* Goal Input */}
            <div className={styles.fieldGroup}>
              <label htmlFor="goal" className={styles.label}>
                <BookOpen size={16} className={styles.labelIcon} />
                <span>Learning Goal or Plan</span>
                <span className={styles.required}>*</span>
              </label>
              <textarea
                id="goal"
                className={styles.textarea}
                rows={3}
                placeholder="e.g. Master FastAPI, asynchronous programming, and SQL database design in Python"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                disabled={isLoading}
                required
              />
              <span className={styles.hint}>
                Be specific about what skills or projects you want to finish.
              </span>
            </div>

            {/* Duration & Daily Capacity Row */}
            <div className={styles.twoColumnRow}>
              {/* Target Duration */}
              <div className={styles.fieldGroup}>
                <label htmlFor="durationDays" className={styles.label}>
                  <Calendar size={16} className={styles.labelIcon} />
                  <span>Target Duration (Days)</span>
                  <span className={styles.required}>*</span>
                </label>
                <input
                  id="durationDays"
                  type="number"
                  min={1}
                  max={365}
                  className={styles.input}
                  value={durationDays}
                  onChange={(e) => setDurationDays(Number(e.target.value))}
                  disabled={isLoading}
                  required
                />
                <span className={styles.hint}>Fixed total days for the entire roadmap.</span>
              </div>

              {/* Daily Available Time */}
              <div className={styles.fieldGroup}>
                <label htmlFor="dailyMinutes" className={styles.label}>
                  <Clock size={16} className={styles.labelIcon} />
                  <span>Daily Time (Minutes)</span>
                  <span className={styles.required}>*</span>
                </label>
                <input
                  id="dailyMinutes"
                  type="number"
                  min={15}
                  max={720}
                  step={15}
                  className={styles.input}
                  value={dailyMinutes}
                  onChange={(e) => setDailyMinutes(Number(e.target.value))}
                  disabled={isLoading}
                  required
                />
                <span className={styles.hint}>e.g. 60m (1 hr), 90m (1.5 hrs), 120m (2 hrs).</span>
              </div>
            </div>

            {/* Optional Context */}
            <div className={styles.fieldGroup}>
              <label htmlFor="context" className={styles.label}>
                <Lightbulb size={16} className={styles.labelIcon} />
                <span>Existing Syllabus or Extra Context (Optional)</span>
              </label>
              <textarea
                id="context"
                className={styles.textarea}
                rows={4}
                placeholder="Paste course outline, specific topics, textbooks, or constraints you want incorporated into the plan..."
                value={context}
                onChange={(e) => setContext(e.target.value)}
                disabled={isLoading}
              />
              <span className={styles.hint}>
                Mira will organize and distribute these topics across your available days.
              </span>
            </div>

            {/* Action Buttons */}
            <div className={styles.actions}>
              <Button
                type="button"
                variant="ghost"
                onClick={() => navigate('/')}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="lg"
                isLoading={isLoading}
                leftIcon={<Sparkles size={18} />}
              >
                {isLoading ? 'Generating Roadmap...' : 'Generate Roadmap'}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
};
