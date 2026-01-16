import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './SupremeCourtMessage.css';

function getShortModelName(model) {
  return model?.split('/')[1] || model || 'Unknown';
}

function JusticeOpinionsTab({ opinions, title }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!opinions || opinions.length === 0) return null;

  return (
    <div className="sc-opinions-section">
      {title && <h4>{title}</h4>}
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

function WithinGroupRankingsDisplay({ stage2, grouping }) {
  const [activeGroup, setActiveGroup] = useState('majority');
  const [activeTab, setActiveTab] = useState(0);

  if (!stage2) return null;

  const groups = [];
  if (stage2.majority_rankings?.rankings?.length > 0) {
    groups.push({ key: 'majority', label: 'Majority Rankings', data: stage2.majority_rankings });
  }
  if (stage2.minority_rankings?.rankings?.length > 0) {
    groups.push({ key: 'minority', label: 'Minority Rankings', data: stage2.minority_rankings });
  }

  if (groups.length === 0) return null;

  const activeData = activeGroup === 'majority'
    ? stage2.majority_rankings
    : stage2.minority_rankings;

  const rankings = activeData?.rankings || [];
  const labelToModel = activeData?.label_to_model || {};

  const deAnonymizeText = (text) => {
    if (!labelToModel || !text) return text;
    let result = text;
    Object.entries(labelToModel).forEach(([label, model]) => {
      const modelShortName = getShortModelName(model);
      result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
    });
    return result;
  };

  return (
    <div className="sc-rankings-section">
      <p className="section-description">
        Each justice evaluated opinions within their own group. Model names shown in <strong>bold</strong> for readability.
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

      {rankings.length > 0 && (
        <>
          <div className="tabs member-tabs">
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
                {deAnonymizeText(rankings[activeTab]?.ranking || '')}
              </ReactMarkdown>
            </div>
            {rankings[activeTab]?.parsed_ranking?.length > 0 && (
              <div className="parsed-ranking">
                <strong>Extracted Ranking:</strong>
                <ol>
                  {rankings[activeTab].parsed_ranking.map((label, i) => (
                    <li key={i}>
                      {labelToModel[label]
                        ? getShortModelName(labelToModel[label])
                        : label}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function SynthesisDisplay({ stage3 }) {
  const [activeTab, setActiveTab] = useState('majority');

  if (!stage3) return null;

  const tabs = [];
  if (stage3.majority) tabs.push({ key: 'majority', label: 'Majority Synthesis' });
  if (stage3.minority) tabs.push({ key: 'minority', label: 'Minority Synthesis' });

  if (tabs.length === 0) return null;

  const activeData = activeTab === 'majority' ? stage3.majority : stage3.minority;

  return (
    <div className="sc-synthesis-section">
      <p className="section-description">
        Group leads synthesized opinions from peer feedback.
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

      {activeData && (
        <div className="tab-content synthesis-content">
          <div className="synthesis-header">
            <span className="synthesis-lead">
              Lead: {getShortModelName(activeData.lead)}
            </span>
            <span className="synthesis-members">
              Group: {activeData.group_members?.map(getShortModelName).join(', ')}
            </span>
          </div>
          <div className="synthesis-opinion markdown-content">
            <ReactMarkdown>{activeData.opinion}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

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
          Joined by: {opinion.group_members?.map(getShortModelName).join(', ')}
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
    clerk: true,
    stage2: false,
    stage3: false,
    final: true,
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const {
    stage1,
    grouping,
    stage2,
    stage3,
    majority_opinion,
    dissent_opinion,
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
          <span>Stage 1: Collecting justice opinions...</span>
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
            <JusticeOpinionsTab opinions={stage1} />
          )}
        </div>
      )}

      {/* Clerk Stage: Grouping */}
      {loading?.clerk && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Clerk: Analyzing and grouping justices...</span>
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

      {/* Stage 2: Within-Group Rankings */}
      {loading?.stage2 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Stage 2: Within-group peer rankings...</span>
        </div>
      )}
      {stage2 && (stage2.majority_rankings || stage2.minority_rankings) && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('stage2')}
          >
            <span className="toggle-icon">{expandedSections.stage2 ? '▼' : '▶'}</span>
            Stage 2: Within-Group Peer Rankings
          </button>
          {expandedSections.stage2 && (
            <WithinGroupRankingsDisplay stage2={stage2} grouping={grouping} />
          )}
        </div>
      )}

      {/* Stage 3: Lead Synthesis */}
      {loading?.stage3 && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>Stage 3: Leads synthesizing opinions...</span>
        </div>
      )}
      {stage3 && (stage3.majority || stage3.minority) && (
        <div className="collapsible-section">
          <button
            className="section-toggle"
            onClick={() => toggleSection('stage3')}
          >
            <span className="toggle-icon">{expandedSections.stage3 ? '▼' : '▶'}</span>
            Stage 3: Lead Synthesis (Draft Opinions)
          </button>
          {expandedSections.stage3 && (
            <SynthesisDisplay stage3={stage3} />
          )}
        </div>
      )}

      {/* Stage 4 & 5: Final Opinions */}
      {(loading?.stage4 || loading?.stage5) && (
        <div className="stage-loading">
          <div className="spinner"></div>
          <span>
            {loading?.stage4 ? 'Stage 4: Completing majority opinion...' : 'Stage 5: Completing dissenting opinion...'}
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
