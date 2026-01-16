import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './SupremeCourtMessage.css';

function getShortModelName(model) {
  return model?.split('/')[1] || model || 'Unknown';
}

// Stage 1: Initial Positions Display
function InitialPositionsTab({ positions }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!positions || positions.length === 0) return null;

  return (
    <div className="sc-positions-section">
      <div className="tabs">
        {positions.map((pos, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {getShortModelName(pos.model)}
          </button>
        ))}
      </div>
      <div className="tab-content">
        <div className="opinion-model">{positions[activeTab].model}</div>
        <div className="opinion-content markdown-content">
          <ReactMarkdown>{positions[activeTab].position}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

// Stage 2: Reconsideration Display
function ReconsiderationDisplay({ reconsiderations }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!reconsiderations || reconsiderations.length === 0) return null;

  const changedCount = reconsiderations.filter(r => r.changed).length;

  return (
    <div className="sc-reconsideration-section">
      <p className="section-description">
        After reading colleagues' positions, {changedCount} of {reconsiderations.length} justices changed their position.
      </p>
      <div className="tabs">
        {reconsiderations.map((recon, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''} ${recon.changed ? 'changed' : 'maintained'}`}
            onClick={() => setActiveTab(index)}
          >
            {getShortModelName(recon.model)}
            <span className={`decision-badge ${recon.changed ? 'changed' : 'maintained'}`}>
              {recon.changed ? 'CHANGED' : 'MAINTAIN'}
            </span>
          </button>
        ))}
      </div>
      <div className="tab-content">
        <div className="opinion-model">{reconsiderations[activeTab].model}</div>
        <div className="reconsideration-decision">
          <span className={`decision-label ${reconsiderations[activeTab].changed ? 'changed' : 'maintained'}`}>
            Decision: {reconsiderations[activeTab].decision}
          </span>
        </div>
        <div className="opinion-content markdown-content">
          <ReactMarkdown>{reconsiderations[activeTab].reconsideration}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

// Clerk Grouping Display
function GroupingDisplay({ grouping }) {
  if (!grouping) return null;

  return (
    <div className="sc-grouping-section">
      <div className={`grouping-result ${grouping.consensus ? 'consensus' : 'split'}`}>
        <div className="grouping-badge">
          {grouping.consensus ? 'UNANIMOUS DECISION' : 'SPLIT DECISION'}
        </div>

        <div className="group-box majority">
          <div className="group-header">
            <span className="group-title">
              {grouping.consensus ? 'All Justices' : `Majority (${grouping.majority?.length || 0} Justices)`}
            </span>
            <span className="group-lead">Lead: {getShortModelName(grouping.majority_lead)}</span>
          </div>
          <div className="group-members">
            {grouping.majority?.map((model, i) => (
              <span key={i} className={`member ${model === grouping.majority_lead ? 'lead' : ''}`}>
                {getShortModelName(model)}
              </span>
            ))}
          </div>
        </div>

        {!grouping.consensus && grouping.minority?.length > 0 && (
          <div className="group-box minority">
            <div className="group-header">
              <span className="group-title">Minority ({grouping.minority?.length || 0} Justices)</span>
              <span className="group-lead">Lead: {getShortModelName(grouping.minority_lead)}</span>
            </div>
            <div className="group-members">
              {grouping.minority?.map((model, i) => (
                <span key={i} className={`member ${model === grouping.minority_lead ? 'lead' : ''}`}>
                  {getShortModelName(model)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <details className="clerk-analysis-details">
        <summary>View Clerk's Full Analysis</summary>
        <div className="clerk-analysis-content markdown-content">
          <ReactMarkdown>{grouping.clerk_analysis}</ReactMarkdown>
        </div>
      </details>
    </div>
  );
}

// Majority Process Display (Draft -> Feedback -> Final)
function MajorityProcessDisplay({ process }) {
  const [activeTab, setActiveTab] = useState('final');

  if (!process) return null;

  return (
    <div className="sc-process-section">
      <p className="section-description">
        Lead ({getShortModelName(process.lead)}) wrote a draft, received feedback from {process.feedback?.length || 0} members, then finalized.
      </p>

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'draft' ? 'active' : ''}`}
          onClick={() => setActiveTab('draft')}
        >
          Draft
        </button>
        <button
          className={`tab ${activeTab === 'feedback' ? 'active' : ''}`}
          onClick={() => setActiveTab('feedback')}
        >
          Feedback ({process.feedback?.length || 0})
        </button>
        <button
          className={`tab ${activeTab === 'final' ? 'active' : ''}`}
          onClick={() => setActiveTab('final')}
        >
          Final Opinion
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'draft' && (
          <div className="draft-opinion markdown-content">
            <ReactMarkdown>{process.draft}</ReactMarkdown>
          </div>
        )}

        {activeTab === 'feedback' && (
          <FeedbackDisplay feedback={process.feedback} />
        )}

        {activeTab === 'final' && (
          <div className="final-opinion markdown-content">
            <ReactMarkdown>{process.final_opinion}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

// Feedback Display
function FeedbackDisplay({ feedback }) {
  const [activeIdx, setActiveIdx] = useState(0);

  if (!feedback || feedback.length === 0) {
    return <p className="no-feedback">No feedback received.</p>;
  }

  return (
    <div className="feedback-section">
      <div className="tabs">
        {feedback.map((fb, index) => (
          <button
            key={index}
            className={`tab ${activeIdx === index ? 'active' : ''}`}
            onClick={() => setActiveIdx(index)}
          >
            {getShortModelName(fb.model)}
          </button>
        ))}
      </div>
      <div className="tab-content">
        <div className="feedback-content markdown-content">
          <ReactMarkdown>{feedback[activeIdx].feedback}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

// Final Opinion Display
function FinalOpinionDisplay({ opinion, type, isConsensus }) {
  if (!opinion || !opinion.opinion) return null;

  const title = type === 'majority'
    ? (isConsensus ? 'Opinion of the Court' : 'Majority Opinion')
    : 'Dissenting Opinion';

  return (
    <div className={`sc-final-opinion ${type}`}>
      <div className="opinion-header">
        <h4>{title}</h4>
        <span className="opinion-author">
          Authored by: {getShortModelName(opinion.lead)}
        </span>
        <span className="opinion-signers">
          Joined by: {opinion.members?.map(getShortModelName).join(', ')}
        </span>
      </div>
      <div className={`final-opinion-text markdown-content ${type}`}>
        <ReactMarkdown>{opinion.opinion}</ReactMarkdown>
      </div>
    </div>
  );
}

export default function SupremeCourtMessage({ message }) {
  const [expandedSections, setExpandedSections] = useState({
    stage1: false,
    stage2: false,
    clerk: true,
    process: false,
    final: true,
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const {
    stage1,
    stage2,
    grouping,
    majority_process,
    majority_opinion,
    dissent_opinion,
    metadata,
    loading
  } = message;

  const isConsensus = grouping?.consensus || metadata?.consensus;
  const votesChanged = metadata?.votes_changed || 0;

  return (
    <div className="supreme-court-message">
      <div className="sc-header">
        <h3>Supreme Court Deliberation</h3>
        <span className="sc-justice-count">9 Justices</span>
      </div>

      {/* Stage 1: Initial Positions */}
      {loading?.stage1 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Stage 1: Collecting initial positions...</span>
        </div>
      )}
      {stage1 && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('stage1')}
          >
            <span className="toggle-icon">{expandedSections.stage1 ? '▼' : '▶'}</span>
            Stage 1: Initial Positions ({stage1.length} justices)
          </button>
          {expandedSections.stage1 && (
            <InitialPositionsTab positions={stage1} />
          )}
        </div>
      )}

      {/* Stage 2: Reconsideration */}
      {loading?.stage2 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Stage 2: Justices reconsidering after reading colleagues...</span>
        </div>
      )}
      {stage2 && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('stage2')}
          >
            <span className="toggle-icon">{expandedSections.stage2 ? '▼' : '▶'}</span>
            Stage 2: Reconsideration ({votesChanged} changed positions)
          </button>
          {expandedSections.stage2 && (
            <ReconsiderationDisplay reconsiderations={stage2} />
          )}
        </div>
      )}

      {/* Clerk Stage: Grouping */}
      {loading?.clerk && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Clerk: Grouping justices...</span>
        </div>
      )}
      {grouping && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('clerk')}
          >
            <span className="toggle-icon">{expandedSections.clerk ? '▼' : '▶'}</span>
            Clerk's Grouping: {isConsensus ? 'Unanimous' : `${grouping.majority?.length || 0}-${grouping.minority?.length || 0} Split`}
          </button>
          {expandedSections.clerk && (
            <GroupingDisplay grouping={grouping} />
          )}
        </div>
      )}

      {/* Stage 3: Majority Opinion Process */}
      {loading?.stage3 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Stage 3: Majority lead drafting with member feedback...</span>
        </div>
      )}
      {majority_process && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('process')}
          >
            <span className="toggle-icon">{expandedSections.process ? '▼' : '▶'}</span>
            Stage 3: Majority Opinion Process (Draft → Feedback → Final)
          </button>
          {expandedSections.process && (
            <MajorityProcessDisplay process={majority_process} />
          )}
        </div>
      )}

      {/* Stage 4 & 5: Final Opinions */}
      {(loading?.stage4 || loading?.stage5) && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>
            {loading?.stage4 ? 'Stage 4: Releasing majority opinion...' : 'Stage 5: Minority writing dissent...'}
          </span>
        </div>
      )}
      {(majority_opinion || dissent_opinion) && (
        <div className="collapsible-section final-section">
          <button
            className="section-toggle final"
            onClick={() => toggleSection('final')}
          >
            <span className="toggle-icon">{expandedSections.final ? '▼' : '▶'}</span>
            {isConsensus ? 'Final: Opinion of the Court' : 'Final: Majority & Dissenting Opinions'}
          </button>
          {expandedSections.final && (
            <div className="final-opinions-container">
              <FinalOpinionDisplay
                opinion={majority_opinion}
                type="majority"
                isConsensus={isConsensus}
              />
              {!isConsensus && dissent_opinion && (
                <FinalOpinionDisplay
                  opinion={dissent_opinion}
                  type="minority"
                  isConsensus={false}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
