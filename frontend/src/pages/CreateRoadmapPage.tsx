import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  Clock,
  Calendar,
  Layers,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Check,
} from 'lucide-react';
import {
  listRoadmaps,
  previewGeneratedRoadmap,
  previewInsertion,
  applyInsertion,
  generateRoadmap,
} from '../api/roadmaps';
import {
  Roadmap,
  GeneratedRoadmap,
  InsertionPreviewResponse,
  RoadmapInsertionRequest,
} from '../types';
import { DEV_USER } from '../utils/devUser';
import { formatMinutes } from '../utils/formatters';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { ErrorBanner } from '../components/common/ErrorBanner';
import styles from './CreateRoadmapPage.module.css';

type Step = 'input' | 'processing' | 'preview' | 'confirmed';
type ApplyMode = 'insert' | 'new';

export const CreateRoadmapPage: React.FC = () => {
  const navigate = useNavigate();

  // Roadmaps for selection and insertion context
  const [allRoadmaps, setAllRoadmaps] = useState<Roadmap[]>([]);
  const [selectedRoadmapId, setSelectedRoadmapId] = useState<number | null>(null);

  // Form input state
  const [content, setContent] = useState('');
  const [title, setTitle] = useState('');
  const [customDuration, setCustomDuration] = useState<number | ''>('');
  const [dailyMinutes, setDailyMinutes] = useState(DEV_USER.dailyAvailableMinutes);

  // Flow & AI state
  const [step, setStep] = useState<Step>('input');
  const [processingStage, setProcessingStage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isApplying, setIsApplying] = useState(false);

  // Preview data
  const [generatedPreview, setGeneratedPreview] = useState<GeneratedRoadmap | null>(null);
  const [insertionPreview, setInsertionPreview] = useState<InsertionPreviewResponse | null>(null);
  const [applyMode, setApplyMode] = useState<ApplyMode>('insert');

  // Load existing roadmaps to determine active roadmap context
  useEffect(() => {
    async function loadRoadmaps() {
      try {
        const roadmaps = await listRoadmaps(DEV_USER.id);
        setAllRoadmaps(roadmaps);
        if (roadmaps.length > 0) {
          setSelectedRoadmapId(roadmaps[0].id);
          setApplyMode('insert');
        } else {
          setSelectedRoadmapId(null);
          setApplyMode('new');
        }
      } catch {
        setAllRoadmaps([]);
        setSelectedRoadmapId(null);
        setApplyMode('new');
      }
    }
    loadRoadmaps();
  }, []);

  const activeRoadmap = useMemo(() => {
    if (!selectedRoadmapId || allRoadmaps.length === 0) return null;
    return allRoadmaps.find((r) => r.id === selectedRoadmapId) || allRoadmaps[0];
  }, [selectedRoadmapId, allRoadmaps]);

  // Smart day count detection from pasted content (e.g. Day 1, Day 2, Day 3)
  const detectedDays = useMemo(() => {
    if (!content.trim()) return null;
    const matches = content.match(/(?:day|level|step)\s*(\d+)[:\s-]/gi);
    if (!matches || matches.length === 0) return null;
    const numbers = matches.map((m) => {
      const match = m.match(/\d+/);
      return match ? parseInt(match[0], 10) : 0;
    });
    const max = Math.max(...numbers);
    return max > 0 && max <= 365 ? max : null;
  }, [content]);

  // Effective duration
  const effectiveDuration = customDuration !== '' ? Number(customDuration) : (detectedDays || 7);

  // Handle AI conceptual step progression during loading
  useEffect(() => {
    let timer1: NodeJS.Timeout;
    let timer2: NodeJS.Timeout;

    if (step === 'processing') {
      setProcessingStage(0);
      timer1 = setTimeout(() => setProcessingStage(1), 900);
      timer2 = setTimeout(() => setProcessingStage(2), 1800);
    }

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, [step]);

  // Step 1 -> Step 2: "Plan with Mira"
  const handlePlanWithMira = async (e: React.FormEvent) => {
    e.preventDefault();

    const raw = content.trim();
    if (!raw) {
      setError('Please paste a roadmap, syllabus, or learning goal.');
      return;
    }

    setError(null);
    setStep('processing');

    // Auto-derive goal/title if not explicitly provided
    const firstLine = raw.split('\n')[0].replace(/^(day\s*\d+[:\s-]*|topic[:\s-]*|#+\s*)/i, '').trim();
    const effectiveGoal = title.trim() || firstLine.slice(0, 120) || 'Custom Learning Plan';

    const requestPayload = {
      user_id: DEV_USER.id,
      goal: effectiveGoal.slice(0, 450),
      target_duration_days: effectiveDuration,
      daily_available_minutes: dailyMinutes,
      context: raw.slice(0, 2000),
    };

    try {
      // Step A: Request AI preview (strictly read-only, 0 DB writes)
      const generated = await previewGeneratedRoadmap(requestPayload);
      setGeneratedPreview(generated);

      // Step B: If user has an active roadmap, simulate insertion impact via deterministic engine
      if (activeRoadmap) {
        try {
          const insertionRequest: RoadmapInsertionRequest = {
            new_days: generated.days.map((d) => ({
              tasks: d.tasks.map((t) => ({
                title: t.title,
                description: t.description,
                estimated_minutes: t.estimated_minutes,
                order_index: t.order_index,
                category: t.category,
              })),
            })),
            metadata: {
              source: 'ai_planning',
              goal: effectiveGoal,
            },
          };

          const insertSim = await previewInsertion(activeRoadmap.id, insertionRequest);
          setInsertionPreview(insertSim);

          if (insertSim.conflict) {
            setApplyMode('new');
          } else {
            setApplyMode('insert');
          }
        } catch {
          // If insertion preview fails, default to standalone new roadmap
          setInsertionPreview(null);
          setApplyMode('new');
        }
      } else {
        setInsertionPreview(null);
        setApplyMode('new');
      }

      setStep('preview');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'AI planning failed. Please try again.';
      setError(msg);
      setStep('input');
    }
  };

  // Step 3 -> Step 4: "Confirm & Apply"
  const handleConfirmAndApply = async () => {
    if (!generatedPreview) return;

    setIsApplying(true);
    setError(null);

    try {
      if (applyMode === 'insert' && activeRoadmap && insertionPreview && !insertionPreview.conflict) {
        // Apply deterministic insertion to active roadmap
        const insertionRequest: RoadmapInsertionRequest = {
          new_days: generatedPreview.days.map((d) => ({
            tasks: d.tasks.map((t) => ({
              title: t.title,
              description: t.description,
              estimated_minutes: t.estimated_minutes,
              order_index: t.order_index,
              category: t.category,
            })),
          })),
          metadata: {
            source: 'ai_planning',
            goal: generatedPreview.title,
          },
        };

        const result = await applyInsertion(activeRoadmap.id, insertionRequest);
        if (result.conflict) {
          setError(result.message || 'Cannot insert: scheduling conflict detected.');
          setIsApplying(false);
          return;
        }
      } else {
        // Create as new standalone roadmap
        await generateRoadmap({
          user_id: DEV_USER.id,
          goal: generatedPreview.title.slice(0, 450),
          target_duration_days: generatedPreview.target_duration_days,
          daily_available_minutes: dailyMinutes,
          context: content.trim().slice(0, 2000),
        });
      }

      // Transition to restrained completion state
      setStep('confirmed');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to apply roadmap changes.';
      setError(msg);
      setIsApplying(false);
    }
  };

  // Metrics for preview
  const totalPreviewMinutes = useMemo(() => {
    if (!generatedPreview) return 0;
    return generatedPreview.days.reduce(
      (sum, d) => sum + d.tasks.reduce((tSum, t) => tSum + t.estimated_minutes, 0),
      0
    );
  }, [generatedPreview]);

  const totalPreviewTasks = useMemo(() => {
    if (!generatedPreview) return 0;
    return generatedPreview.days.reduce((sum, d) => sum + d.tasks.length, 0);
  }, [generatedPreview]);

  const avgDailyMinutes = generatedPreview
    ? Math.round(totalPreviewMinutes / generatedPreview.days.length)
    : 0;

  return (
    <div className="container">
      <div className={styles.wrapper}>
        {error && <ErrorBanner message={error} onRetry={() => setError(null)} />}

        {/* ========================================================================= */}
        {/* STEP 1: INPUT STATE                                                      */}
        {/* ========================================================================= */}
        {step === 'input' && (
          <>
            <header className={styles.header}>
              <span className={styles.category}>AI Planning</span>
              <h1 className={styles.title}>Add something to your plan.</h1>
              <p className={styles.subtitle}>
                Paste a roadmap, course outline, study plan, or anything you already decided to complete.
              </p>
            </header>

            <Card padding="lg" className={styles.formCard}>
              <form onSubmit={handlePlanWithMira} className={styles.form}>
                {/* Roadmap Selection (if user has roadmaps) */}
                {allRoadmaps.length > 0 && (
                  <div className={styles.roadmapSelectGroup}>
                    <label htmlFor="roadmap-select" className={styles.roadmapSelectLabel}>
                      Add to:
                    </label>
                    <select
                      id="roadmap-select"
                      className={styles.roadmapSelect}
                      value={selectedRoadmapId || ''}
                      onChange={(e) => setSelectedRoadmapId(Number(e.target.value))}
                    >
                      {allRoadmaps.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.title} ({r.target_duration_days} days)
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Large Content Textarea */}
                <div className={styles.fieldGroup}>
                  <div className={styles.labelRow}>
                    <label htmlFor="content-input" className={styles.label}>
                      <FileText size={16} className={styles.labelIcon} />
                      <span>Plan Content or Outline</span>
                      <span className={styles.required}>*</span>
                    </label>
                    <span className={styles.charHint}>
                      {content.length > 0 && `${content.length} characters`}
                    </span>
                  </div>

                  <textarea
                    id="content-input"
                    className={styles.mainTextarea}
                    rows={8}
                    placeholder={`e.g.\nDay 1:\nPython variables and data types\nPractice 5 basic problems\n\nDay 2:\nConditional statements and branches\nPractice exercises\n\nDay 3:\nLoops and iterations\nSolve 10 problems`}
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    required
                  />
                  <div className={styles.hintBar}>
                    <span>
                      {detectedDays ? (
                        <strong className={styles.detectedBadge}>
                          Detected {detectedDays} days in your outline
                        </strong>
                      ) : (
                        'Paste your syllabus, topic list, or day-by-day outline.'
                      )}
                    </span>
                  </div>
                </div>

                {/* Optional Configuration Controls */}
                <div className={styles.configGrid}>
                  {/* Optional Title */}
                  <div className={styles.fieldGroup}>
                    <label htmlFor="title-input" className={styles.label}>
                      <span>Plan Title (Optional)</span>
                    </label>
                    <input
                      id="title-input"
                      type="text"
                      className={styles.input}
                      placeholder="e.g. Python Fundamentals"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      maxLength={150}
                    />
                  </div>

                  {/* Optional Target Duration */}
                  <div className={styles.fieldGroup}>
                    <label htmlFor="duration-input" className={styles.label}>
                      <Calendar size={15} className={styles.labelIcon} />
                      <span>Target Duration (Days)</span>
                    </label>
                    <input
                      id="duration-input"
                      type="number"
                      min={1}
                      max={365}
                      className={styles.input}
                      placeholder={detectedDays ? `${detectedDays} (detected)` : '7'}
                      value={customDuration}
                      onChange={(e) =>
                        setCustomDuration(e.target.value === '' ? '' : Math.max(1, Number(e.target.value)))
                      }
                    />
                  </div>

                  {/* Optional Daily Available Time */}
                  <div className={styles.fieldGroup}>
                    <label htmlFor="capacity-input" className={styles.label}>
                      <Clock size={15} className={styles.labelIcon} />
                      <span>Daily Time (Minutes)</span>
                    </label>
                    <input
                      id="capacity-input"
                      type="number"
                      min={15}
                      max={720}
                      step={15}
                      className={styles.input}
                      value={dailyMinutes}
                      onChange={(e) => setDailyMinutes(Math.max(15, Number(e.target.value)))}
                    />
                  </div>
                </div>

                {/* Action Bar */}
                <div className={styles.actions}>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => navigate('/')}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="lg"
                    leftIcon={<Sparkles size={18} />}
                  >
                    Plan with Mira
                  </Button>
                </div>
              </form>
            </Card>
          </>
        )}

        {/* ========================================================================= */}
        {/* STEP 2: AI PROCESSING STATE                                              */}
        {/* ========================================================================= */}
        {step === 'processing' && (
          <div className={styles.processingWrapper} aria-live="polite">
            <Card padding="lg" className={styles.processingCard}>
              <div className={styles.pulsingIconArea}>
                <Sparkles size={40} className={styles.pulsingSparkle} />
              </div>

              <div className={styles.processingTextGroup}>
                <h2 className={styles.processingTitle}>
                  {processingStage === 0 && 'Understanding your plan…'}
                  {processingStage === 1 && 'Structuring your tasks…'}
                  {processingStage >= 2 && 'Preparing your roadmap…'}
                </h2>
                <p className={styles.processingSubtitle}>
                  Converting your content into structured, day-wise actionable levels.
                </p>
              </div>

              <div className={styles.shimmerBar} />
            </Card>
          </div>
        )}

        {/* ========================================================================= */}
        {/* STEP 3: PREVIEW STATE ("Here’s what Mira understood.")                    */}
        {/* ========================================================================= */}
        {step === 'preview' && generatedPreview && (
          <>
            <header className={styles.header}>
              <span className={styles.category}>AI Interpretation</span>
              <h1 className={styles.title}>Here’s what Mira understood.</h1>
              <p className={styles.subtitle}>
                Review how Mira organized your plan before applying it. Nothing is saved until you confirm.
              </p>
            </header>

            {/* Metrics Overview Card */}
            <Card padding="lg" className={styles.metricsCard}>
              <div className={styles.metricsHeader}>
                <div className={styles.titleCluster}>
                  <span className={styles.metricsTag}>Proposed Plan</span>
                  <h2 className={styles.planTitle}>{generatedPreview.title}</h2>
                  {generatedPreview.description && (
                    <p className={styles.planDesc}>{generatedPreview.description}</p>
                  )}
                </div>
                <Badge variant="current" dot>
                  {generatedPreview.target_duration_days} Days
                </Badge>
              </div>

              <div className={styles.metricsRow}>
                <div className={styles.metricItem}>
                  <span className={styles.metricLabel}>Total Duration</span>
                  <span className={styles.metricValue}>
                    {generatedPreview.target_duration_days} Days
                  </span>
                </div>

                <div className={styles.metricItem}>
                  <span className={styles.metricLabel}>Total Tasks</span>
                  <span className={styles.metricValue}>{totalPreviewTasks} Tasks</span>
                </div>

                <div className={styles.metricItem}>
                  <span className={styles.metricLabel}>Total Workload</span>
                  <span className={styles.metricValue}>{formatMinutes(totalPreviewMinutes)}</span>
                </div>

                <div className={styles.metricItem}>
                  <span className={styles.metricLabel}>Daily Workload</span>
                  <span className={styles.metricValue}>~{formatMinutes(avgDailyMinutes)} / day</span>
                </div>
              </div>
            </Card>

            {/* =================================================================== */}
            {/* SECTION 5: "Where this will go" INSERTION VISUALIZER                */}
            {/* =================================================================== */}
            {activeRoadmap && (
              <Card
                padding="md"
                className={`${styles.impactCard} ${
                  insertionPreview?.conflict ? styles.impactCardConflict : ''
                }`}
              >
                <div className={styles.impactHeader}>
                  <div className={styles.impactTitleGroup}>
                    <Layers size={18} className={styles.impactIcon} />
                    <h3 className={styles.impactTitle}>
                      Where this will go in <strong>{activeRoadmap.title}</strong>
                    </h3>
                  </div>

                  {insertionPreview?.conflict ? (
                    <Badge variant="danger" dot>
                      Capacity Conflict
                    </Badge>
                  ) : (
                    <Badge variant="completed" dot>
                      Insertion Ready
                    </Badge>
                  )}
                </div>

                {/* Conflict State (Section 6) */}
                {insertionPreview?.conflict ? (
                  <div className={styles.conflictBox}>
                    <AlertTriangle size={20} className={styles.conflictIcon} />
                    <div className={styles.conflictContent}>
                      <h4 className={styles.conflictHeading}>
                        {insertionPreview.conflict_reason === 'INSUFFICIENT_CAPACITY'
                          ? 'Insertion Exceeds Fixed Duration'
                          : 'Scheduling Conflict Detected'}
                      </h4>
                      <p className={styles.conflictMsg}>
                        {insertionPreview.message ||
                          'Adding these days exceeds your remaining roadmap capacity.'}
                      </p>
                      <p className={styles.conflictActionsHint}>
                        You can adjust your plan duration, review your current roadmap, or create this as a separate standalone roadmap.
                      </p>
                      <div className={styles.conflictButtons}>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setStep('input')}
                        >
                          Adjust plan
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate('/roadmap')}
                        >
                          Review roadmap
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : insertionPreview ? (
                  /* Visual Insertion Timeline Mapping (Section 5) */
                  <div className={styles.insertionVisualizer}>
                    {/* Current Completed History */}
                    <div className={styles.timelineBlock}>
                      <span className={styles.timelineBlockTitle}>Current Roadmap (Locked History):</span>
                      <div className={styles.timelinePills}>
                        {insertionPreview.first_incomplete_day && insertionPreview.first_incomplete_day > 1 ? (
                          Array.from({ length: insertionPreview.first_incomplete_day - 1 }).map((_, i) => (
                            <span key={i} className={styles.historyPill}>
                              Day {i + 1} <Check size={12} className={styles.checkMini} />
                            </span>
                          ))
                        ) : (
                          <span className={styles.neutralPill}>No days completed yet</span>
                        )}
                        <span className={styles.markerPill}>
                          Day {insertionPreview.insertion_start_day || insertionPreview.first_incomplete_day || 1} ← First incomplete day
                        </span>
                      </div>
                    </div>

                    {/* New Content Insertion */}
                    <div className={styles.timelineBlock}>
                      <span className={styles.timelineBlockTitle}>New Content:</span>
                      <div className={styles.newContentList}>
                        {generatedPreview.days.map((d, i) => {
                          const targetDayNumber =
                            (insertionPreview.insertion_start_day || insertionPreview.first_incomplete_day || 1) + i;
                          return (
                            <div key={d.day_number} className={styles.newDayMappingRow}>
                              <span className={styles.newDaySource}>Day {targetDayNumber}</span>
                              <span className={styles.arrowIcon}>→</span>
                              <span className={styles.newDayTarget}>
                                New Day {d.day_number}: {d.title || `Part ${d.day_number}`}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Existing Future Work Shifts */}
                    {insertionPreview.shifted_days && insertionPreview.shifted_days.length > 0 && (
                      <div className={styles.timelineBlock}>
                        <span className={styles.timelineBlockTitle}>Existing Future Work Shifted:</span>
                        <div className={styles.shiftedDaysList}>
                          {insertionPreview.shifted_days.map((shift) => (
                            <span key={shift.day_id} className={styles.shiftPill}>
                              Day {shift.old_day_number} → Day {shift.new_day_number}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}

                {/* Mode Selector */}
                <div className={styles.modeSelector}>
                  <label
                    className={`${styles.modeOption} ${
                      applyMode === 'insert' ? styles.modeSelected : ''
                    } ${insertionPreview?.conflict ? styles.modeDisabled : ''}`}
                  >
                    <input
                      type="radio"
                      name="applyMode"
                      value="insert"
                      checked={applyMode === 'insert'}
                      onChange={() => setApplyMode('insert')}
                      disabled={Boolean(insertionPreview?.conflict)}
                    />
                    <div>
                      <span className={styles.modeTitle}>
                        Add to current roadmap ({activeRoadmap.title})
                      </span>
                      <span className={styles.modeDesc}>
                        Inserts starting at Day {insertionPreview?.insertion_start_day || 1} and shifts future tasks forward.
                      </span>
                    </div>
                  </label>

                  <label
                    className={`${styles.modeOption} ${
                      applyMode === 'new' ? styles.modeSelected : ''
                    }`}
                  >
                    <input
                      type="radio"
                      name="applyMode"
                      value="new"
                      checked={applyMode === 'new'}
                      onChange={() => setApplyMode('new')}
                    />
                    <div>
                      <span className={styles.modeTitle}>
                        Create as new standalone roadmap
                      </span>
                      <span className={styles.modeDesc}>
                        Creates a fresh {generatedPreview.target_duration_days}-day roadmap dedicated solely to this plan.
                      </span>
                    </div>
                  </label>
                </div>
              </Card>
            )}

            {/* Day-by-Day Task Breakdown */}
            <div className={styles.breakdownSection}>
              <h3 className={styles.breakdownHeader}>Daily Tasks Breakdown</h3>

              <div className={styles.daysList}>
                {generatedPreview.days.map((day) => {
                  const dayMinutes = day.tasks.reduce((sum, t) => sum + t.estimated_minutes, 0);

                  return (
                    <Card key={day.day_number} padding="md" className={styles.previewDayCard}>
                      <div className={styles.dayCardHeader}>
                        <div className={styles.dayCardTitleRow}>
                          <span className={styles.dayTag}>Day {day.day_number}</span>
                          <h4 className={styles.dayCardTitle}>
                            {day.title || `Day ${day.day_number}`}
                          </h4>
                        </div>
                        <span className={styles.dayDurationBadge}>
                          {formatMinutes(dayMinutes)}
                        </span>
                      </div>

                      <div className={styles.tasksList}>
                        {day.tasks.map((task, idx) => (
                          <div key={idx} className={styles.previewTaskRow}>
                            <div className={styles.taskMarker}>
                              <CheckCircle2 size={16} className={styles.checkOutline} />
                            </div>
                            <div className={styles.taskDetails}>
                              <div className={styles.taskHeading}>
                                <span className={styles.taskTitle}>{task.title}</span>
                                {task.category && (
                                  <span className={styles.taskCatBadge}>
                                    {task.category}
                                  </span>
                                )}
                              </div>
                              {task.description && (
                                <p className={styles.taskDescription}>
                                  {task.description}
                                </p>
                              )}
                              <span className={styles.taskTime}>
                                <Clock size={11} />
                                <span>{formatMinutes(task.estimated_minutes)}</span>
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>

            {/* Confirmation Controls (Section 7) */}
            <div className={styles.previewActions}>
              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={() => setStep('input')}
                leftIcon={<ArrowLeft size={16} />}
                disabled={isApplying}
              >
                Back
              </Button>

              <Button
                type="button"
                variant="primary"
                size="lg"
                onClick={handleConfirmAndApply}
                isLoading={isApplying}
                rightIcon={<ArrowRight size={16} />}
              >
                {isApplying
                  ? 'Applying Changes...'
                  : applyMode === 'insert'
                  ? 'Add to roadmap'
                  : 'Create roadmap'}
              </Button>
            </div>
          </>
        )}

        {/* ========================================================================= */}
        {/* STEP 4: RESTRAINED SATISFYING CONFIRMATION STATE (Section 7)              */}
        {/* ========================================================================= */}
        {step === 'confirmed' && (
          <div className={styles.confirmedWrapper} aria-live="polite">
            <Card padding="lg" className={styles.confirmedCard}>
              <div className={styles.confirmedIconArea}>
                <CheckCircle2 size={44} className={styles.confirmedCheckIcon} />
              </div>

              <div className={styles.confirmedTextGroup}>
                <h2 className={styles.confirmedTitle}>
                  {applyMode === 'insert' ? 'Added to your roadmap.' : 'Roadmap created.'}
                </h2>
                <p className={styles.confirmedSubtitle}>
                  {applyMode === 'insert'
                    ? 'Your new days have been scheduled starting at your current incomplete day.'
                    : 'Your structured day-wise level progression is ready.'}
                </p>
              </div>

              <Button
                variant="primary"
                size="lg"
                onClick={() => navigate('/roadmap')}
                rightIcon={<ArrowRight size={16} />}
              >
                Continue to roadmap
              </Button>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};
