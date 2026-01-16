import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './SupremeCourtMessage.css';

function getShortModelName(model) {
  return model?.split('/')[1] || model || 'Unknown';
}

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel || !text) return text;

  let result = text;
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = getShortModelName(model);
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

function JusticeOpinionsTab({ opinions, title }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!opinions || opinions.length === 0) return null;

  return (
    <div className="sc-opinions-section">
      <h4>{title}</h4>
      <div className="tabs">
        {opinions.map((opinion, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {getShortModelName(opinion.model)}
          </button>
        ))}
      </div>
      <div className="tab-content">
        <div className="opinion-model">{opinions[activeTab].model}</div>
        <div className="opinion-content markdown-content">
          <ReactMarkdown>{opinions[activeTab].response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

function RankingsTab({ rankings, labelToModel }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!rankings || rankings.length === 0) return null;

  return (
    <div className="sc-rankings-section">
      <h4>Peer Rankings</h4>
      <p className="section-description">
        Each justice evaluated all opinions anonymously. Model names shown in <strong>bold</strong> for readability.
      </p>
      <div className="tabs">
        {rankings.map((rank, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {getShortModelName(rank.model)}
          </button>
        ))}
      </div>
      <div className="tab-content">
        <div className="ranking-content markdown-content">
          <ReactMarkdown>
            {deAnonymizeText(rankings[activeTab].ranking, labelToModel)}
          </ReactMarkdown>
        </div>
        {rankings[activeTab].parsed_ranking?.length > 0 && (
          <div className="parsed-ranking">
            <strong>Extracted Ranking:</strong>
            <ol>
              {rankings[activeTab].parsed_ranking.map((label, i) => (
                <li key={i}>
                  {labelToModel?.[label]
                    ? getShortModelName(labelToModel[label])
                    : label}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  );
}

function GroupingDisplay({ grouping }) {
  if (!grouping) return null;

  return (
    <div className="sc-grouping-section">
      <h4>Clerk's Analysis</h4>
      <div className={`grouping-result ${grouping.consensus ? 'consensus' : 'split'}`}>
        <div className="grouping-badge">
          {grouping.consensus ? 'UNANIMOUS' : 'SPLIT DECISION'}
        </div>

        <div className="group-box majority">
          <div className="group-header">
            <span className="group-title">Majority ({grouping.majority?.length || 0} Justices)</span>
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

function DraftOpinionsDisplay({ draftOpinions }) {
  const [activeTab, setActiveTab] = useState('majority');

  if (!draftOpinions) return null;

  const tabs = [];
  if (draftOpinions.majority_draft) tabs.push({ key: 'majority', label: 'Majority Draft' });
  if (draftOpinions.minority_draft) tabs.push({ key: 'minority', label: 'Minority Draft' });

  const activeDraft = activeTab === 'majority'
    ? draftOpinions.majority_draft
    : draftOpinions.minority_draft;

  return (
    <div className="sc-draft-opinions-section">
      <h4>Draft Opinions</h4>
      <p className="section-description">
        Group leads synthesized their group's views into draft opinions.
      </p>

      {tabs.length > 1 && (
        <div className="tabs">
          {tabs.map(tab => (
            <button
              key={tab.key}
              className={`tab ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {activeDraft && (
        <div className="tab-content draft-content">
          <div className="draft-header">
            <span className="draft-lead">
              Written by: {getShortModelName(activeDraft.lead)}
            </span>
            <span className="draft-members">
              Representing: {activeDraft.group_members?.map(getShortModelName).join(', ')}
            </span>
          </div>
          <div className="draft-opinion markdown-content">
            <ReactMarkdown>{activeDraft.opinion}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

function RatingsDisplay({ ratings }) {
  const [activeGroup, setActiveGroup] = useState('majority');
  const [activeTab, setActiveTab] = useState(0);

  if (!ratings) return null;

  const groups = [];
  if (ratings.majority_ratings?.length > 0) groups.push({ key: 'majority', label: 'Majority Ratings' });
  if (ratings.minority_ratings?.length > 0) groups.push({ key: 'minority', label: 'Minority Ratings' });

  if (groups.length === 0) return null;

  const activeRatings = activeGroup === 'majority'
    ? ratings.majority_ratings
    : ratings.minority_ratings;

  return (
    <div className="sc-ratings-section">
      <h4>Peer Review of Draft Opinions</h4>
      <p className="section-description">
        Group members rated their lead's draft opinion.
      </p>

      {groups.length > 1 && (
        <div className="tabs group-tabs">
          {groups.map(group => (
            <button
              key={group.key}
              className={`tab ${activeGroup === group.key ? 'active' : ''}`}
              onClick={() => { setActiveGroup(group.key); setActiveTab(0); }}
            >
              {group.label}
            </button>
          ))}
        </div>
      )}

      {activeRatings && activeRatings.length > 0 && (
        <>
          <div className="tabs member-tabs">
            {activeRatings.map((rating, index) => (
              <button
                key={index}
                className={`tab ${activeTab === index ? 'active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {getShortModelName(rating.model)}
                {rating.rating && <span className="rating-badge">{rating.rating}/10</span>}
              </button>
            ))}
          </div>
          <div className="tab-content rating-content">
            <div className="rating-score">
              Rating: <strong>{activeRatings[activeTab].rating || 'N/A'}</strong>/10
            </div>
            <div className="rating-feedback markdown-content">
              <ReactMarkdown>{activeRatings[activeTab].feedback}</ReactMarkdown>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function FinalOpinionsDisplay({ finalOpinions, isConsensus }) {
  const [activeTab, setActiveTab] = useState('majority');

  if (!finalOpinions) return null;

  const tabs = [];
  if (finalOpinions.majority_opinion) tabs.push({ key: 'majority', label: isConsensus ? 'Opinion of the Court' : 'Majority Opinion' });
  if (finalOpinions.minority_opinion) tabs.push({ key: 'minority', label: 'Dissenting Opinion' });

  const activeOpinion = activeTab === 'majority'
    ? finalOpinions.majority_opinion
    : finalOpinions.minority_opinion;

  return (
    <div className="sc-final-opinions-section">
      <h4>{isConsensus ? 'Opinion of the Court' : 'Final Opinions'}</h4>

      {tabs.length > 1 && (
        <div className="tabs">
          {tabs.map(tab => (
            <button
              key={tab.key}
              className={`tab ${activeTab === tab.key ? 'active' : ''} ${tab.key}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {activeOpinion && (
        <div className={`tab-content final-opinion-content ${activeTab}`}>
          <div className="opinion-header">
            <span className="opinion-author">
              Authored by: {getShortModelName(activeOpinion.lead)}
            </span>
            {activeOpinion.average_rating && (
              <span className="opinion-rating">
                Peer Rating: {activeOpinion.average_rating.toFixed(1)}/10
              </span>
            )}
            <span className="opinion-signers">
              Joined by: {activeOpinion.group_members?.map(getShortModelName).join(', ')}
            </span>
          </div>
          <div className={`final-opinion-text markdown-content ${activeTab}`}>
            <ReactMarkdown>{activeOpinion.opinion}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SupremeCourtMessage({ message }) {
  const [expandedSections, setExpandedSections] = useState({
    stage1: false,
    stage2: false,
    grouping: true,
    drafts: false,
    ratings: false,
    final: true,
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const {
    stage1,
    stage2,
    grouping,
    draft_opinions,
    ratings,
    final_opinions,
    metadata,
    loading
  } = message;

  const isConsensus = grouping?.consensus || metadata?.consensus;

  return (
    <div className="supreme-court-message">
      <div className="sc-header">
        <h3>Supreme Court Deliberation</h3>
        <span className="sc-justice-count">9 Justices</span>
      </div>

      {/* Stage 1: Individual Opinions */}
      {loading?.stage1 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Collecting justice opinions...</span>
        </div>
      )}
      {stage1 && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('stage1')}
          >
            <span className="toggle-icon">{expandedSections.stage1 ? '▼' : '▶'}</span>
            Stage 1: Individual Justice Opinions ({stage1.length} responses)
          </button>
          {expandedSections.stage1 && (
            <JusticeOpinionsTab opinions={stage1} title="" />
          )}
        </div>
      )}

      {/* Stage 2: Peer Rankings */}
      {loading?.stage2 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Justices ranking opinions...</span>
        </div>
      )}
      {stage2 && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('stage2')}
          >
            <span className="toggle-icon">{expandedSections.stage2 ? '▼' : '▶'}</span>
            Stage 2: Peer Rankings ({stage2.length} evaluations)
          </button>
          {expandedSections.stage2 && (
            <RankingsTab rankings={stage2} labelToModel={metadata?.label_to_model} />
          )}
        </div>
      )}

      {/* Clerk Stage: Grouping */}
      {loading?.clerk && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Clerk analyzing and grouping justices...</span>
        </div>
      )}
      {grouping && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('grouping')}
          >
            <span className="toggle-icon">{expandedSections.grouping ? '▼' : '▶'}</span>
            Clerk's Grouping: {isConsensus ? 'Unanimous' : 'Split Decision'}
          </button>
          {expandedSections.grouping && (
            <GroupingDisplay grouping={grouping} />
          )}
        </div>
      )}

      {/* Stage 3: Draft Opinions */}
      {loading?.stage3 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Leads writing draft opinions...</span>
        </div>
      )}
      {draft_opinions && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('drafts')}
          >
            <span className="toggle-icon">{expandedSections.drafts ? '▼' : '▶'}</span>
            Stage 3: Draft Opinions
          </button>
          {expandedSections.drafts && (
            <DraftOpinionsDisplay draftOpinions={draft_opinions} />
          )}
        </div>
      )}

      {/* Stage 4: Ratings */}
      {loading?.stage4 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Group members rating draft opinions...</span>
        </div>
      )}
      {ratings && (ratings.majority_ratings?.length > 0 || ratings.minority_ratings?.length > 0) && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('ratings')}
          >
            <span className="toggle-icon">{expandedSections.ratings ? '▼' : '▶'}</span>
            Stage 4: Peer Review of Drafts
          </button>
          {expandedSections.ratings && (
            <RatingsDisplay ratings={ratings} />
          )}
        </div>
      )}

      {/* Stage 5: Final Opinions */}
      {loading?.stage5 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Leads synthesizing final opinions...</span>
        </div>
      )}
      {final_opinions && (
        <div className="collapsible-section final-section">
          <button
            className="section-toggle final"
            onClick={() => toggleSection('final')}
          >
            <span className="toggle-icon">{expandedSections.final ? '▼' : '▶'}</span>
            {isConsensus ? 'Final: Opinion of the Court' : 'Final: Majority & Dissenting Opinions'}
          </button>
          {expandedSections.final && (
            <FinalOpinionsDisplay finalOpinions={final_opinions} isConsensus={isConsensus} />
          )}
        </div>
      )}
    </div>
  );
}
