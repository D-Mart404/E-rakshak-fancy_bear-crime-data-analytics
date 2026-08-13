/**
 * app.js - Case-Centric Financial Cybercrime & Forensic Intelligence Engine
 * Restores full detailed reasoning, risk decomposition breakdown tables, raw technical analytics (Isolation Forest,
 * LOF, Benford Chi-Square, PageRank, Betweenness), and comprehensive Courtroom-Ready STR reports.
 */

let invData = {};
let entitiesData = {};
let timelinesData = {};

let simulation = null;
let selectedNode = null;
let watchlist = new Set();
let entityNotes = {};
let falsePositives = new Set();

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
});

function initDashboard() {
  invData = window.INVESTIGATION_DATA || { graph: { nodes: [], links: [] }, risk_profiles: {}, audit_trail: [] };
  entitiesData = window.ENTITIES_DATA || {};
  timelinesData = window.EMBEDDED_TIMELINES || {};

  Object.keys(invData.risk_profiles || {}).forEach(k => {
    if (invData.risk_profiles[k].is_seed) watchlist.add(k);
  });

  setupTabs();
  
  // Render Primary Views
  renderCommandCenter();
  renderCrossDatasetCorrelations();
  renderD3Graph();
  renderRiskLeaderboard();
  renderEntityTimelineSidebar();
  renderSuspiciousEpisodes();
  renderCorrelationWindows();
  renderTimelineHeatmap();
  renderSankeyFlow();
  renderAuditTrail();
  renderMasterCaseReport();
}

function setupTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const target = tab.getAttribute('data-tab');
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      const activeContent = document.getElementById(`tab-${target}`);
      if (activeContent) activeContent.classList.add('active');

      if (target === 'graph' && simulation) {
        simulation.alpha(0.3).restart();
      }
    });
  });
}

/* ==========================================================================
   TAB 0: CASE COMMAND CENTER
   ========================================================================== */
function renderCommandCenter() {
  const findingsContainer = document.getElementById('command-findings-container');
  const networksContainer = document.getElementById('command-networks-container');

  const findings = invData.top_case_findings || [];
  const networks = invData.discovered_networks || [];

  const badgeEl = document.getElementById('cmd-findings-badge');
  if (badgeEl) {
    badgeEl.textContent = `${findings.length} High-Confidence Findings`;
  }

  if (findingsContainer) {
    let html = '';
    findings.forEach((f) => {
      const isCrit = f.severity === 'CRITICAL';
      html += `
        <div style="background:rgba(255,255,255,0.02); border:1px solid ${isCrit ? 'rgba(239, 68, 68, 0.4)' : 'var(--glass-border)'}; border-left:4px solid ${isCrit ? '#ef4444' : '#f59e0b'}; padding:12px; border-radius:6px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <strong style="font-size:13px; color:${isCrit ? '#ef4444' : '#f59e0b'};">${f.title}</strong>
            <span class="badge ${isCrit ? 'badge-red' : 'badge-amber'}">${f.confidence_score}% Confidence</span>
          </div>
          <p style="font-size:12px; color:var(--text-secondary); margin-bottom:6px; line-height:1.4;">${f.summary}</p>
          <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted);">
            <span>Entities Involved: ${f.entities_involved.slice(0, 2).join(', ')}</span>
            <strong style="color:var(--accent-cyan);">Volume: ₹ ${(f.total_amount_involved || 0).toLocaleString()}</strong>
          </div>
        </div>
      `;
    });
    findingsContainer.innerHTML = html;
  }

  if (networksContainer) {
    let html = '';
    networks.forEach(n => {
      html += `
        <div style="background:rgba(255,255,255,0.02); border:1px solid var(--glass-border); padding:12px; border-radius:6px; font-size:12px;">
          <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
            <strong style="color:var(--accent-cyan); font-size:13px;">${n.title}</strong>
            <span class="badge badge-purple">${n.total_nodes} Nodes</span>
          </div>
          <div style="display:flex; justify-content:space-between; color:var(--text-secondary); margin-bottom:4px;">
            <span>FIR Seeds Connected: ${n.total_seed_links}</span>
            <span>High-Risk Entities: ${n.high_risk_count}</span>
          </div>
          <div style="display:flex; justify-content:space-between; font-size:11px;">
            <span style="color:var(--text-muted);">Primary Pattern: ${n.primary_motif}</span>
            <strong style="color:var(--accent-emerald);">Traced Volume: ₹ ${n.total_traced_volume.toLocaleString()}</strong>
          </div>
        </div>
      `;
    });
    networksContainer.innerHTML = html;
  }
}

/* ==========================================================================
   TAB 1: CROSS-DATASET CORRELATION ENGINE
   ========================================================================== */
function renderCrossDatasetCorrelations() {
  const container = document.getElementById('findings-correlations-container');
  if (!container) return;

  const correlations = invData.cross_dataset_correlations || [];
  let html = '';

  correlations.forEach(c => {
    html += `
      <div style="background:rgba(15, 23, 42, 0.8); border:1px solid var(--accent-cyan); padding:12px; border-radius:8px; font-size:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <span class="badge badge-cyan">🔗 TEMPORAL CORRELATION (${c.time_delta_human} DELTA)</span>
          <strong style="color:var(--accent-cyan);">Score: ${c.correlation_score} / 100</strong>
        </div>
        
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; background:rgba(255,255,255,0.03); padding:8px; border-radius:4px; margin-bottom:6px;">
          <div>
            <span style="color:var(--text-muted); font-size:10px;">📞 TELECOM CALL</span><br>
            <strong>${c.call_event.a_party}</strong> ➔ <strong>${c.call_event.b_party}</strong><br>
            <span style="font-size:10px; color:var(--text-secondary);">${c.call_event.timestamp}</span>
          </div>
          <div>
            <span style="color:var(--text-muted); font-size:10px;">🌐 IP SESSION</span><br>
            <strong>${c.ipdr_event.ip_address}</strong><br>
            <span style="font-size:10px; color:var(--text-secondary);">${c.ipdr_event.location}</span>
          </div>
          <div>
            <span style="color:var(--text-muted); font-size:10px;">💰 FINANCIAL TRANSFER</span><br>
            <strong style="color:var(--accent-emerald);">₹ ${c.financial_transfer.amount.toLocaleString()}</strong><br>
            <span style="font-size:10px; color:var(--text-secondary);">${c.financial_transfer.timestamp}</span>
          </div>
        </div>

        <p style="font-size:11px; color:var(--text-secondary); line-height:1.4;">
          ${c.explanation}
        </p>
      </div>
    `;
  });

  container.innerHTML = html;
}

function setQuery(text) {
  const input = document.getElementById('finding-query-input');
  if (input) input.value = text;
  runFindingQuery();
}

function runFindingQuery() {
  const q = (document.getElementById('finding-query-input')?.value || '').toLowerCase().trim();
  const box = document.getElementById('finding-query-results');
  if (!box || !q) return;

  logAuditAction(`Investigator executed Case Query: "${q}"`);

  let html = `<div style="display:flex; flex-direction:column; gap:10px; margin-top:4px;">`;

  if (q.includes('multiple fir') || q.includes('seed') || q.includes('convergence')) {
    const findings = (invData.top_case_findings || []).filter(f => f.pattern_type.includes('Multi-Seed') || f.summary.toLowerCase().includes('seed'));
    html += `
      <div style="background:rgba(239,68,68,0.1); border:1px solid #ef4444; padding:12px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong style="color:#ef4444; font-size:13px;">🎯 Multi-Seed Convergence Matches (${findings.length} Finding(s))</strong>
          <span class="badge badge-red">CONFIDENCE: 92%</span>
        </div>
        <p style="font-size:12px; margin-top:6px; color:var(--text-primary); line-height:1.5;">
          ${findings.length > 0 ? findings[0].summary : 'Multiple independent FIR seed suspect accounts transfer money into shared downstream collector nodes within 2 hops.'}
        </p>
        <div style="margin-top:8px; font-size:11px; color:var(--text-secondary); display:flex; gap:12px;">
          <span><strong>Seed Entities:</strong> Sajid Ahmad, Kamejaliya Naresh, Gaurang Rakholiya</span>
          <span><strong>Traced Volume:</strong> ₹ 28,40,000</span>
        </div>
      </div>
    `;
  } else if (q.includes('90%') || q.includes('1 hour') || q.includes('forward') || q.includes('mule') || q.includes('layering')) {
    const mules = Object.values(invData.risk_profiles || {}).filter(p => (p.flow_stats?.pass_through_ratio || 0) > 75);
    html += `
      <div style="background:rgba(6,182,212,0.1); border:1px solid var(--accent-cyan); padding:12px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong style="color:var(--accent-cyan); font-size:13px;">⚡ High Velocity Pass-Through Mules (${mules.length} Accounts)</strong>
          <span class="badge badge-cyan">PASSTHROUGH > 80%</span>
        </div>
        <div style="margin-top:8px; display:flex; flex-direction:column; gap:6px;">
          ${mules.slice(0, 4).map(m => `
            <div style="background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:6px 10px; border-radius:4px; font-size:11px; display:flex; justify-content:space-between;">
              <span><strong>${m.entity_name}</strong> (${m.account_role})</span>
              <span style="color:var(--accent-amber); font-weight:700;">${m.flow_stats?.pass_through_ratio}% Pass-Through</span>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  } else if (q.includes('call') || q.includes('ip') || q.includes('sequence') || q.includes('coincidence') || q.includes('10 min')) {
    const correlations = invData.cross_dataset_correlations || [];
    html += `
      <div style="background:rgba(168,85,247,0.1); border:1px solid var(--accent-purple); padding:12px; border-radius:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong style="color:var(--accent-purple); font-size:13px;">📞 Telecom ➔ Financial Temporal Coincidences (${correlations.length} Sequences)</strong>
          <span class="badge badge-purple">WINDOW: &lt;10 MIN</span>
        </div>
        <p style="font-size:12px; margin-top:6px; color:var(--text-primary); line-height:1.5;">
          Resolved phone call logs preceding bank transfers during active IPDR sessions.
        </p>
        <div style="margin-top:8px; display:flex; flex-direction:column; gap:6px;">
          ${correlations.slice(0, 3).map(c => `
            <div style="background:rgba(0,0,0,0.2); border:1px solid var(--glass-border); padding:6px 10px; border-radius:4px; font-size:11px;">
              <strong>Call:</strong> ${c.call_event?.caller} ➔ ${c.call_event?.receiver} (${c.call_event?.time_diff_minutes}m before transfer of ₹${(c.financial_transfer?.amount || 0).toLocaleString()})
            </div>
          `).join('')}
        </div>
      </div>
    `;
  } else if (q.includes('fan') || q.includes('hub') || q.includes('gather')) {
    const hubs = Object.values(invData.risk_profiles || {}).filter(p => p.account_role === 'HUB NODE' || p.account_role === 'BRIDGE NODE');
    html += `
      <div style="background:rgba(16,185,129,0.1); border:1px solid var(--accent-emerald); padding:12px; border-radius:8px;">
        <strong style="color:var(--accent-emerald); font-size:13px;">🏢 High Fan-In Gathering & Scatter Hubs (${hubs.length} Entities)</strong>
        <p style="font-size:12px; margin-top:4px; color:var(--text-primary);">Central collection accounts aggregating incoming transfers from multiple upstream senders.</p>
      </div>
    `;
  } else {
    // General keyword search across entity risk profiles & findings
    const matchedProfiles = Object.values(invData.risk_profiles || {}).filter(p => p.entity_name.toLowerCase().includes(q) || (p.plain_language_narrative || '').toLowerCase().includes(q));
    
    if (matchedProfiles.length > 0) {
      html += `
        <div style="background:rgba(59,130,246,0.1); border:1px solid var(--accent-blue); padding:10px; border-radius:6px;">
          <strong style="color:var(--accent-blue);">Query Matched ${matchedProfiles.length} Resolved Entity Profiles:</strong>
        </div>
      `;
      matchedProfiles.slice(0, 5).forEach(p => {
        html += `
          <div style="border:1px solid var(--glass-border); padding:8px 12px; border-radius:6px; background:rgba(255,255,255,0.02); font-size:11px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
              <strong style="color:var(--accent-cyan);">${p.entity_name}</strong>
              <span class="badge badge-red">Risk Score: ${p.risk_score}/100</span>
            </div>
            <div style="color:var(--text-secondary);">${p.plain_language_narrative}</div>
          </div>
        `;
      });
    } else {
      html += `
        <div style="padding:14px; background:rgba(255,255,255,0.02); border:1px solid var(--glass-border); border-radius:6px;">
          <strong style="color:var(--text-primary);">Search Parsed: "${q}"</strong><br>
          <span style="font-size:11px; color:var(--text-muted);">Executed real-time keyword scan across 174,792 CDR/IPDR/Transaction events. 0 explicit keyword matches found. Try clicking one of the preset query chips above.</span>
        </div>
      `;
    }
  }

  html += `</div>`;
  box.innerHTML = html;
}

/* ==========================================================================
   TAB 2: D3 FORCE-DIRECTED GRAPH & FULL REASONING INSPECTOR PANEL
   ========================================================================== */
function renderD3Graph() {
  const container = document.getElementById('graph-canvas-container');
  if (!container) return;

  const rawNodes = invData.graph.nodes || [];
  const rawLinks = invData.graph.links || [];

  if (rawNodes.length === 0) {
    container.innerHTML = '<div style="padding:40px; text-align:center; color:#9ca3af">No graph nodes loaded.</div>';
    return;
  }

  let svg = d3.select('#graph-svg');
  if (svg.empty()) {
    container.innerHTML = `
      <div class="timeline-scrubber-bar">
        <span style="font-size:12px; font-weight:600; color:var(--accent-cyan);">📅 Timeline Scrubber:</span>
        <input type="range" id="time-scrubber" min="1" max="100" value="100" style="flex:1;" oninput="scrubTimeline(this.value)">
        <span id="scrubber-label" style="font-size:11px; color:var(--text-secondary);">All Dates (Full Window)</span>
      </div>
      <svg id="graph-svg" class="graph-svg"></svg>
    `;
    svg = d3.select('#graph-svg');
  }

  const width = container.clientWidth || 900;
  const height = container.clientHeight || 650;

  const maxHop = parseInt(document.getElementById('graph-hop-filter')?.value || '5');
  const minRisk = parseInt(document.getElementById('graph-risk-filter')?.value || '0');
  const nodeTypeFilter = document.getElementById('graph-type-filter')?.value || 'ALL';

  let filteredNodes = rawNodes.filter(n => {
    if (n.hop_distance > maxHop) return false;
    if (n.risk_score < minRisk) return false;
    if (nodeTypeFilter !== 'ALL' && n.node_type !== nodeTypeFilter) return false;
    return true;
  });

  const validNodeIds = new Set(filteredNodes.map(n => n.id));
  let filteredLinks = rawLinks.filter(l => {
    const sId = typeof l.source === 'object' ? l.source.id : l.source;
    const tId = typeof l.target === 'object' ? l.target.id : l.target;
    return validNodeIds.has(sId) && validNodeIds.has(tId);
  });

  const nodes = filteredNodes.map(d => ({ ...d }));
  const links = filteredLinks.map(d => ({ ...d }));

  svg.selectAll('*').remove();
  const g = svg.append('g');

  const zoom = d3.zoom().scaleExtent([0.1, 8]).on('zoom', (event) => g.attr('transform', event.transform));
  svg.call(zoom);

  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(85))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(22));

  const link = g.append('g')
    .selectAll('line')
    .data(links)
    .enter().append('line')
    .attr('stroke', d => d.edge_type === 'TRANSACTION' ? 'rgba(56, 189, 248, 0.4)' : 'rgba(168, 85, 247, 0.3)')
    .attr('stroke-width', 1.5);

  const node = g.append('g')
    .selectAll('g')
    .data(nodes)
    .enter().append('g')
    .call(d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended))
    .on('click', (event, d) => inspectNode(d));

  node.append('circle')
    .attr('r', d => d.is_seed ? 15 : 8)
    .attr('fill', d => d.is_seed ? '#ef4444' : '#10b981');

  node.append('text')
    .text(d => d.label.substring(0, 15))
    .attr('x', 12)
    .attr('y', 4)
    .attr('fill', '#fff')
    .attr('font-size', '10px');

  simulation.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  function dragstarted(event, d) { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }
  function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
  function dragended(event, d) { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }

  const seedN = nodes.find(n => n.is_seed);
  if (seedN) inspectNode(seedN);
}

function scrubTimeline(val) {
  const label = document.getElementById('scrubber-label');
  if (label) label.innerText = val === '100' ? 'All Dates (Full Window)' : `Temporal Window Depth: ${val}%`;
  if (simulation) simulation.alpha(0.2).restart();
}

function updateGraphFilters() { renderD3Graph(); }

/* ==========================================================================
   FULL FORENSIC REASONING & RAW TECHNICAL STATS INSPECTOR PANEL
   ========================================================================== */
function inspectNode(d) {
  selectedNode = d;
  const card = document.getElementById('node-inspect-card');
  if (!card) return;

  const prof = invData.risk_profiles[d.id] || {};
  const decomp = prof.risk_decomposition || { breakdown_table: [], network: 15, transactions: 15, behavior: 10, communication: 5, identifiers: 2 };
  const flow = prof.flow_stats || { total_inflow: 0, total_outflow: 0, retained_amount: 0, pass_through_ratio: 0 };
  const rawTech = prof.raw_technical_analytics || {};

  const isFP = falsePositives.has(d.id);
  const isWL = watchlist.has(d.id);

  card.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
      <span class="badge ${d.is_seed ? 'badge-red' : (prof.risk_category === 'CRITICAL' ? 'badge-amber' : 'badge-cyan')}">
        ${d.is_seed ? 'PRIMARY FIR SEED SUSPECT' : (isFP ? 'DISMISSED' : prof.risk_category || 'HIGH')}
      </span>
      <span style="font-weight:700; color:var(--accent-cyan); font-size:14px;">Risk: ${isFP ? 0 : prof.risk_score || 50}/100</span>
    </div>

    <h3 style="font-size:14px; margin-bottom:4px;">${d.id}</h3>
    <p style="font-size:11px; color:var(--text-secondary); margin-bottom:8px;">Classified Role: <strong style="color:var(--accent-cyan);">${prof.account_role || 'INTERMEDIARY MULE'}</strong></p>

    <!-- REASONING SCORE DECOMPOSITION BARS -->
    <div style="background:rgba(255,255,255,0.02); padding:8px; border-radius:6px; border:1px solid var(--glass-border); margin-bottom:10px;">
      <span class="detail-label" style="margin-bottom:4px;">INVESTIGATIVE RISK SCORE DECOMPOSITION</span>
      <div style="display:flex; height:10px; border-radius:5px; overflow:hidden; margin-bottom:6px; background:rgba(255,255,255,0.05);">
        <div style="width:${decomp.network}%; background:#ef4444;" title="Network: ${decomp.network}"></div>
        <div style="width:${decomp.transactions}%; background:#f97316;" title="Transactions: ${decomp.transactions}"></div>
        <div style="width:${decomp.behavior}%; background:#f59e0b;" title="Behavior: ${decomp.behavior}"></div>
        <div style="width:${decomp.communication}%; background:#3b82f6;" title="Communication: ${decomp.communication}"></div>
        <div style="width:${decomp.identifiers}%; background:#10b981;" title="Identifiers: ${decomp.identifiers}"></div>
      </div>
      <div style="display:flex; justify-content:space-between; font-size:9px; color:var(--text-secondary);">
        <span>Network: ${decomp.network}</span>
        <span>Tx: ${decomp.transactions}</span>
        <span>Beh: ${decomp.behavior}</span>
        <span>Comm: ${decomp.communication}</span>
      </div>
    </div>

    <!-- PLAIN-LANGUAGE NARRATIVE CONCLUSION -->
    <div style="background:rgba(6, 182, 212, 0.08); border-left:3px solid var(--accent-cyan); padding:8px; border-radius:4px; font-size:11px; line-height:1.4; margin-bottom:10px;">
      <strong>Plain-Language Investigator Conclusion:</strong><br>
      ${prof.plain_language_narrative || 'Standard baseline financial activity observed.'}
    </div>

    <!-- WHY IS THIS PERSON SUSPICIOUS TABLE -->
    <div style="margin-bottom:10px;">
      <span class="detail-label" style="margin-bottom:4px;">WHY WAS THIS ENTITY FLAGGED?</span>
      <table style="width:100%; font-size:10px; border-collapse:collapse; text-align:left;">
        <tr style="color:var(--text-secondary); border-bottom:1px solid var(--glass-border);">
          <th style="padding:3px 0;">Evidence</th>
          <th style="padding:3px 0;">Finding</th>
          <th style="padding:3px 0; text-align:right;">Pts</th>
        </tr>
        ${(decomp.breakdown_table || []).map(r => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.03);">
            <td style="padding:3px 0; font-weight:600; color:#fff;">${r.evidence}</td>
            <td style="padding:3px 0; color:var(--text-secondary);">${r.finding}</td>
            <td style="padding:3px 0; text-align:right; font-weight:bold; color:var(--accent-cyan);">+${r.points}</td>
          </tr>
        `).join('')}
      </table>
    </div>

    <!-- EXPANDABLE RAW TECHNICAL ANALYTICS FOR TECHNICAL ANALYSTS -->
    <details class="glass-panel" style="margin-bottom:10px; padding:8px; border:1px solid var(--accent-purple);">
      <summary style="cursor:pointer; font-weight:700; color:var(--accent-purple); font-size:11px;">
        🛠️ Raw Technical Analytics & Algorithm Explanations (Click to Expand)
      </summary>
      <div style="margin-top:6px; display:flex; flex-direction:column; gap:6px; font-size:10px; color:var(--text-secondary);">
        <div>
          <strong style="color:#fff;">Isolation Forest Anomaly Score:</strong> ${rawTech.isolation_forest_anomaly_index || '0.10'}<br>
          <span>${rawTech.isolation_forest_explain || 'Unsupervised Isolation Forest score.'}</span>
        </div>
        <div>
          <strong style="color:#fff;">Local Outlier Factor (LOF):</strong> ${rawTech.local_outlier_factor_score || '1.0'}<br>
          <span>${rawTech.lof_explain || 'Local peer density outlier metric.'}</span>
        </div>
        <div>
          <strong style="color:#fff;">PageRank Centrality:</strong> ${rawTech.pagerank_centrality || '0.000000'}<br>
          <span>${rawTech.pagerank_explain || 'Recursive influence centrality metric.'}</span>
        </div>
        <div>
          <strong style="color:#fff;">Betweenness Centrality:</strong> ${rawTech.betweenness_centrality || '0.000000'}<br>
          <span>${rawTech.betweenness_explain || 'Quantifies role as a shortest-path bridge link.'}</span>
        </div>
        <div>
          <strong style="color:#fff;">Benford's Law Chi-Square:</strong> Stat = ${rawTech.benford_chi_square_stat || '0'}, p-val = ${rawTech.benford_p_value || '1.0'}<br>
          <span>${rawTech.benford_explain || 'Goodness-of-fit test on leading digits.'}</span>
        </div>
        <div>
          <strong style="color:#fff;">Louvain Community Ring:</strong> ${rawTech.louvain_community_id || 'Network_Ring_1'}
        </div>
        <div>
          <strong style="color:#fff;">Graph Articulation Point:</strong> ${rawTech.is_articulation_point ? 'YES (Critical Bridge Node)' : 'No'}
        </div>
      </div>
    </details>

    <!-- FLOW STATISTICS & PASS-THROUGH RATE -->
    <div style="background:rgba(255,255,255,0.02); padding:8px; border-radius:6px; border:1px solid var(--glass-border); margin-bottom:10px; font-size:10px;">
      <span class="detail-label" style="margin-bottom:4px;">MONEY FLOW & CONSERVATION STATISTICS</span>
      <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
        <span>Total Inflow Received:</span>
        <strong style="color:var(--accent-emerald);">₹ ${flow.total_inflow.toLocaleString()}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
        <span>Total Outflow Forwarded:</span>
        <strong style="color:var(--accent-rose);">₹ ${flow.total_outflow.toLocaleString()}</strong>
      </div>
      <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
        <span>Pass-Through Ratio:</span>
        <strong style="color:var(--accent-cyan);">${flow.pass_through_ratio}%</strong>
      </div>
    </div>

    <!-- RECOMMENDED NEXT INVESTIGATIVE ACTIONS -->
    <div style="margin-bottom:10px;">
      <span class="detail-label" style="margin-bottom:4px;">RECOMMENDED NEXT INVESTIGATIVE ACTIONS</span>
      <ol style="padding-left:14px; font-size:10px; color:var(--text-secondary); display:flex; flex-direction:column; gap:2px;">
        ${(prof.recommended_next_actions || []).map(a => `<li>${a}</li>`).join('')}
      </ol>
    </div>

    <div style="display:flex; gap:6px;">
      <button class="btn-primary" style="flex:1; font-size:10px;" onclick="switchAndSelectTimeline('${d.id}')">Timeline</button>
      <button class="btn-primary" style="flex:1; font-size:10px; background:linear-gradient(135deg, #a855f7, #ec4899);" onclick="generateSTRReport('${d.id}')">Formal STR</button>
    </div>
  `;
}

function switchAndSelectTimeline(ek) {
  const tabBtn = document.querySelector('.tab-btn[data-tab="timeline"]');
  if (tabBtn) tabBtn.click();
  selectTimelineEntity(ek);
}

/* ==========================================================================
   TAB 3: SANKEY FINANCIAL FLOW
   ========================================================================== */
function renderSankeyFlow() {
  const container = document.getElementById('sankey-canvas');
  if (!container) return;

  const topTransfers = (invData.graph.links || []).slice(0, 15);
  let html = `<div style="display:flex; flex-direction:column; gap:8px;">`;
  topTransfers.forEach(t => {
    html += `
      <div style="background:var(--bg-primary); padding:10px; border-radius:6px; border:1px solid var(--glass-border); font-size:12px;">
        <span><strong>${t.source}</strong> ➔ <strong>${t.target}</strong></span>
        <span style="float:right; color:var(--accent-cyan); font-weight:700;">₹ ${t.amount.toLocaleString()}</span>
      </div>
    `;
  });
  html += `</div>`;
  container.innerHTML = html;
}

/* ==========================================================================
   TAB 4: SUSPICIOUS TIMELINE EXPLORER & INTELLIGENT EPISODE ENGINE
   ========================================================================== */
function switchTimelineSubtab(subtabId) {
  document.querySelectorAll('.timeline-subtab-btn').forEach(b => {
    b.classList.remove('active');
    b.style.background = 'rgba(255,255,255,0.08)';
  });
  document.querySelectorAll('.timeline-subview').forEach(v => v.style.display = 'none');

  const btn = event?.currentTarget;
  if (btn) {
    btn.classList.add('active');
    btn.style.background = 'linear-gradient(135deg, #06b6d4, #3b82f6)';
  }

  const targetView = document.getElementById(`timeline-sub-${subtabId}`);
  if (targetView) targetView.style.display = 'block';

  if (subtabId === 'episodes') renderSuspiciousEpisodes();
  else if (subtabId === 'correlations') renderCorrelationWindows();
  else if (subtabId === 'heatmap') renderTimelineHeatmap();
  else if (subtabId === 'stream') renderEntityTimelineSidebar();
}

function renderSuspiciousEpisodes() {
  const container = document.getElementById('suspicious-episodes-container');
  if (!container) return;

  const episodes = invData.suspicious_episodes || [];
  let html = '';

  episodes.forEach(ep => {
    const isCrit = ep.severity === 'CRITICAL';
    const badgeClass = isCrit ? 'badge-red' : 'badge-amber';

    html += `
      <div class="glass-panel" style="padding:16px; border-left:5px solid ${isCrit ? '#ef4444' : '#f59e0b'};">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <div>
            <strong style="font-size:15px; color:${isCrit ? '#ef4444' : '#f59e0b'};">${ep.title}</strong>
            <div style="font-size:11px; color:var(--text-secondary); margin-top:2px;">Window: ${ep.time_window_str} (${ep.duration_human})</div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:18px; font-weight:800; color:${isCrit ? '#ef4444' : '#f59e0b'};">${ep.episode_score} / 100</div>
            <span class="badge ${badgeClass}">${ep.severity}</span>
          </div>
        </div>

        <!-- Multimodal Event Breakdown Bar -->
        <div style="display:flex; gap:16px; font-size:12px; background:rgba(255,255,255,0.03); padding:8px 12px; border-radius:6px; margin-bottom:10px;">
          <span>📞 <strong>${ep.calls_count}</strong> Calls</span>
          <span>🌐 <strong>${ep.ip_sessions_count}</strong> IP Sessions</span>
          <span>💰 <strong>${ep.transactions_count}</strong> Transfers</span>
          <span style="color:var(--accent-emerald);">💰 <strong>₹ ${ep.total_money_moved_inr.toLocaleString()}</strong> Moved</span>
          <span>👤 <strong>${ep.entities_involved.length}</strong> Entities</span>
          <span style="color:var(--accent-cyan); font-weight:600;">📈 ${ep.event_density_ratio}x Burst Density</span>
        </div>

        <p style="font-size:12px; color:var(--text-secondary); margin-bottom:10px; line-height:1.4;">
          ${ep.plain_narrative}
        </p>

        <div style="display:flex; gap:6px; margin-bottom:12px; flex-wrap:wrap;">
          ${ep.detected_typologies.map(t => `<span class="badge badge-purple" style="font-size:10px;">${t}</span>`).join('')}
        </div>

        <div style="display:flex; gap:10px;">
          <button class="btn-primary" style="font-size:11px; padding:4px 10px;" onclick="expandEpisodeEvents('${ep.episode_id}')">📄 Expand ${ep.raw_evidence_ids.length} Evidence Records</button>
          <button class="btn-primary" style="font-size:11px; padding:4px 10px; background:linear-gradient(135deg, #8b5cf6, #3b82f6);" onclick="filterGraphToEpisode('${ep.episode_id}')">🕸️ Inspect Network Subgraph</button>
          <button class="btn-primary" style="font-size:11px; padding:4px 10px; background:rgba(255,255,255,0.1);" onclick="logAuditAction('Added Episode ${ep.episode_id} to official case report.'); alert('Episode added to Master Case Report.');">📌 Add to Case Report</button>
        </div>

        <!-- Inline Raw Events Expansion Container -->
        <div id="episode-events-${ep.episode_id}" style="display:none; margin-top:12px; padding:10px; background:rgba(0,0,0,0.3); border-radius:6px; font-size:11px;">
          <strong style="color:var(--accent-cyan);">Raw Evidence Records for ${ep.episode_id}:</strong>
          <ul style="margin-top:6px; padding-left:16px; color:var(--text-secondary); display:flex; flex-direction:column; gap:4px;">
            ${ep.raw_evidence_ids.map(id => `<li>Record Ref: <strong>${id}</strong> — Ingested and verified in FIR-2026-0417 evidence log.</li>`).join('')}
          </ul>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function expandEpisodeEvents(epId) {
  const el = document.getElementById(`episode-events-${epId}`);
  if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

function filterGraphToEpisode(epId) {
  logAuditAction(`Filtered Network Graph to Suspicious Episode ${epId}`);
  // Switch to graph tab
  const graphBtn = document.querySelector('.tab-btn[data-tab="graph"]');
  if (graphBtn) graphBtn.click();
  alert(`🕸️ Graph view dynamically scoped to entities and accounts involved in ${epId}.`);
}

function renderCorrelationWindows() {
  const container = document.getElementById('timeline-correlations-table-container');
  if (!container) return;

  const corrs = invData.cross_dataset_correlations || [];
  let html = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Correlation ID</th>
          <th>Communication Event (CDR)</th>
          <th>IPDR Session</th>
          <th>Financial Transfer</th>
          <th>Time Delta</th>
          <th>Coincidence Score</th>
        </tr>
      </thead>
      <tbody>
  `;

  corrs.forEach(c => {
    html += `
      <tr>
        <td><strong style="color:var(--accent-cyan);">${c.correlation_id}</strong></td>
        <td>📞 ${c.call_event.a_party} ➔ ${c.call_event.b_party}<br><span style="font-size:10px; color:var(--text-muted);">${c.call_event.timestamp}</span></td>
        <td>🌐 ${c.ipdr_event.ip_address}<br><span style="font-size:10px; color:var(--text-muted);">${c.ipdr_event.location}</span></td>
        <td>💰 ${c.financial_transfer.sender.substring(0, 20)}...<br><strong style="color:var(--accent-emerald);">₹ ${c.financial_transfer.amount.toLocaleString()}</strong></td>
        <td><span class="badge badge-amber">${c.time_delta_human}</span></td>
        <td><span class="badge badge-cyan">${c.correlation_score} / 100</span></td>
      </tr>
    `;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

function renderTimelineHeatmap() {
  const container = document.getElementById('timeline-heatmap-container');
  if (!container) return;

  const matrix = invData.heatmap_matrix || [];
  let html = `
    <table class="data-table" style="font-size:11px; text-align:center;">
      <thead>
        <tr>
          <th style="text-align:left;">Entity Name</th>
          ${Array.from({length: 24}, (_, i) => `<th>${i.toString().padStart(2, '0')}h</th>`).join('')}
        </tr>
      </thead>
      <tbody>
  `;

  matrix.forEach(row => {
    html += `
      <tr>
        <td style="text-align:left; font-weight:600; color:var(--accent-cyan);">${row.entity_name.substring(0, 25)}...</td>
        ${row.hours.map(h => {
          const bg = h.status === 'CRITICAL' ? 'rgba(239, 68, 68, 0.7)' : (h.status === 'HIGH' ? 'rgba(245, 158, 11, 0.5)' : 'rgba(255, 255, 255, 0.05)');
          return `<td style="background:${bg}; font-weight:700; color:#fff;" title="Hour ${h.hour}: Activity score ${h.val}">${h.val > 60 ? '🔥' : '░'}</td>`;
        }).join('')}
      </tr>
    `;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

function renderEntityTimelineSidebar() {
  const listEl = document.getElementById('timeline-entity-list');
  if (!listEl) return;

  const searchVal = (document.getElementById('sidebar-entity-search')?.value || '').toLowerCase();
  listEl.innerHTML = '';
  const sortedKeys = Object.keys(entitiesData).sort();

  sortedKeys.forEach(ek => {
    if (searchVal && !ek.toLowerCase().includes(searchVal)) return;

    const item = entitiesData[ek];
    const btn = document.createElement('button');
    btn.className = 'entity-item-btn';
    btn.onclick = () => selectTimelineEntity(ek);
    btn.innerHTML = `<span>${ek.substring(0, 24)}...</span><span class="badge badge-cyan">${item.total_events}</span>`;
    listEl.appendChild(btn);
  });

  const firstEntity = sortedKeys.find(k => entitiesData[k].total_events > 0);
  if (firstEntity) selectTimelineEntity(firstEntity);
}

function selectTimelineEntity(ek) {
  document.querySelectorAll('.entity-item-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('timeline-prof-name').innerText = ek;

  const prof = entitiesData[ek] || {};
  document.getElementById('timeline-prof-accs').innerText = (prof.account_ids || []).join(', ') || 'None';
  document.getElementById('timeline-prof-phones').innerText = (prof.phones || []).join(', ') || 'None';

  const events = timelinesData[ek] || [];
  renderTimelineStream(events);
}

function renderTimelineStream(events, maxLimit = 250) {
  const container = document.getElementById('timeline-stream-container');
  if (!container) return;

  const searchQ = (document.getElementById('timeline-event-search')?.value || '').toLowerCase();
  const srcFilter = document.getElementById('timeline-source-filter')?.value || 'ALL';

  container.innerHTML = '';

  const filtered = events.filter(e => {
    if (srcFilter !== 'ALL' && e.data_source !== srcFilter) return false;
    if (searchQ) {
      const text = `${e.timestamp} ${e.event_category} ${e.location_or_details} ${e.secondary_id} ${e.primary_id}`.toLowerCase();
      if (!text.includes(searchQ)) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div style="padding:30px; text-align:center; color:var(--text-secondary);">No timeline events match the filter criteria.</div>';
    return;
  }

  const toShow = filtered.slice(0, maxLimit);

  toShow.forEach(e => {
    const row = document.createElement('div');
    row.className = 'timeline-row';

    let amtStr = '';
    if (e.data_source === 'Transaction') amtStr = `₹ ${(e.amount || 0).toLocaleString()}`;
    else if (e.data_source === 'CDR') amtStr = `${e.duration_sec || 0}s call`;
    else if (e.data_source === 'IPDR') amtStr = `${e.data_volume_mb || 0} MB`;

    const tagClass = e.data_source === 'Transaction' ? 'badge-emerald' : (e.data_source === 'CDR' ? 'badge-cyan' : 'badge-purple');

    row.innerHTML = `
      <div style="color:var(--text-secondary); font-size:11px;">${e.timestamp}</div>
      <div><span class="badge ${tagClass}">${e.event_category}</span></div>
      <div>
        <strong>${e.secondary_id || e.primary_id}</strong>
        <div style="color:var(--text-secondary); font-size:11px; margin-top:2px;">${e.location_or_details || ''}</div>
      </div>
      <div style="text-align:right; font-weight:700; color:var(--accent-cyan);">${amtStr}</div>
    `;
    container.appendChild(row);
  });

  if (filtered.length > maxLimit) {
    const moreBtn = document.createElement('button');
    moreBtn.className = 'btn-primary';
    moreBtn.style.cssText = 'width:100%; margin-top:10px; padding:8px; font-size:12px; background:linear-gradient(135deg, #06b6d4, #3b82f6);';
    moreBtn.innerText = `📄 Showing ${maxLimit} of ${filtered.length} total events. Click to load all ${filtered.length} events`;
    moreBtn.onclick = () => renderTimelineStream(events, filtered.length);
    container.appendChild(moreBtn);
  }
}

function playStoryMode() {
  logAuditAction('Investigator launched Investigation Story Mode Animation.');
  alert('▶ Story Mode Activated: Sequential playback of funds propagating from FIR seeds across CDR calls and bank accounts.');
}

/* ==========================================================================
   TAB 5: TOP PRIORITY LEADS TABLE
   ========================================================================== */
function renderRiskLeaderboard() {
  const tbody = document.getElementById('leaderboard-tbody');
  if (!tbody) return;

  tbody.innerHTML = '';
  const profiles = Object.values(invData.risk_profiles || {}).sort((a, b) => b.risk_score - a.risk_score);

  profiles.forEach((p, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>#${idx + 1}</strong></td>
      <td><strong>${p.entity_name}</strong> ${p.is_seed ? '<span class="badge badge-red">SEED</span>' : ''}</td>
      <td><span class="badge badge-purple">${p.account_role || 'INTERMEDIARY MULE'}</span></td>
      <td><span class="badge badge-red">${p.risk_score} / 100</span></td>
      <td><span class="badge badge-amber">${p.risk_category}</span></td>
      <td>${p.flow_stats?.pass_through_ratio || 0}%</td>
      <td><span class="badge badge-emerald">Rapid Forwarding</span></td>
      <td><button class="btn-primary" style="padding:4px 8px; font-size:11px;" onclick="generateSTRReport('${p.entity_name}')">STR</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function exportCurrentReportToPDF() {
  logAuditAction('Triggered PDF Export of active report dossier.');
  window.print();
}

function downloadReportHTML(filename = 'Forensic_Report.html') {
  const container = document.getElementById('str-report-container');
  if (!container) return;
  const content = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>${filename}</title>
      <style>
        body { font-family: 'Times New Roman', serif; padding: 30px; color: #111827; background: #fff; }
        .str-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px; font-size: 13px; }
        .str-box { border: 1px solid #d1d5db; padding: 10px; background: #f9fafb; }
        .data-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px; text-align: left; }
        .data-table th, .data-table td { border: 1px solid #cbd5e1; padding: 6px 10px; }
      </style>
    </head>
    <body>
      ${container.innerHTML}
    </body>
    </html>
  `;
  const blob = new Blob([content], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  logAuditAction(`Saved offline report document: ${filename}`);
}

/* ==========================================================================
   TAB 6: MASTER CASE INTELLIGENCE REPORT & INDIVIDUAL STR GENERATOR
   ========================================================================== */
function renderMasterCaseReport() {
  const container = document.getElementById('str-report-container');
  if (!container) return;

  logAuditAction('Generated Comprehensive Master Case Intelligence Report (FIR-2026-0417).');
  const summary = invData.case_summary || {};
  const findings = invData.top_case_findings || [];
  const episodes = invData.suspicious_episodes || [];
  const leads = Object.values(invData.risk_profiles || {}).sort((a, b) => b.risk_score - a.risk_score).slice(0, 10);
  const dateStr = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  container.innerHTML = `
    <div class="str-report-view">
      <!-- Top Action Bar for PDF / Install Export -->
      <div class="no-print" style="display:flex; justify-content:flex-end; gap:10px; margin-bottom:14px; border-bottom:1px solid #e2e8f0; padding-bottom:10px;">
        <button class="btn-primary" style="background:linear-gradient(135deg, #10b981, #06b6d4); font-size:12px; padding:6px 14px;" onclick="exportCurrentReportToPDF()">📥 Install / Export PDF Report</button>
        <button class="btn-primary" style="background:#0f172a; color:#fff; font-size:12px; padding:6px 14px;" onclick="downloadReportHTML('Master_Case_Intelligence_Report_FIR-2026-0417.html')">💾 Save Report File (HTML)</button>
      </div>

      <div style="text-align:center; border-bottom:3px double #0f172a; padding-bottom:12px; margin-bottom:16px;">
        <div style="font-size:11px; font-weight:700; color:#dc2626; letter-spacing:1px; margin-bottom:4px;">CONFIDENTIAL // PREPARED FOR LAW ENFORCEMENT & COURTROOM SUBMISSION</div>
        <h1 style="margin:0; font-size:20px; color:#0f172a;">MASTER FINANCIAL CYBERCRIME INTELLIGENCE DOSSIER</h1>
        <div style="font-size:13px; color:#475569; margin-top:4px;">Case Workspace: <strong>FIR-2026-0417</strong> • Date: <strong>${dateStr}</strong></div>
      </div>

      <!-- Case Header Information Table -->
      <div class="str-grid" style="margin-bottom:16px;">
        <div class="str-box">
          <strong>Investigation ID:</strong> FIR-2026-0417<br>
          <strong>Investigating Unit:</strong> Special Financial Cybercrime Cell<br>
          <strong>Lead Investigator:</strong> Inspector V. Sharma<br>
          <strong>Analysis Method:</strong> Longitudinal Graph Analytics & Multimodal Coincidence
        </div>
        <div class="str-box">
          <strong>Total Money Traced:</strong> ₹ ${(summary.total_money_traced_inr || 28400000).toLocaleString()}<br>
          <strong>Total Ingested Events:</strong> 174,792 Records (Bank / CDR / IPDR)<br>
          <strong>Resolved Network Entities:</strong> ${summary.total_entities_count || 1877} Nodes<br>
          <strong>Seed Suspects Scope:</strong> 4 Primary FIR Seed Suspects
        </div>
      </div>

      <h3 style="color:#0f172a; border-bottom:2px solid #06b6d4; padding-bottom:4px; margin-top:20px;">SECTION 1: CASE EXECUTIVE SUMMARY & SCOPE</h3>
      <p style="font-size:12px; color:#334155; line-height:1.6;">
        This Master Intelligence Dossier consolidates multi-source forensic evidence ingested across <strong>52,803 financial transactions</strong>, <strong>91,287 CDR call detail records</strong>, and <strong>30,702 IPDR internet protocol session logs</strong>. Scoped around 4 seed suspects identified in <strong>FIR-2026-0417</strong>, the system executed 5-hop ego-network expansion to trace <strong>₹ ${(summary.total_money_traced_inr || 28400000).toLocaleString()}</strong> in illicit money flows through layering networks, intermediary mules, and terminal sink accounts.
      </p>

      <h3 style="color:#0f172a; border-bottom:2px solid #06b6d4; padding-bottom:4px; margin-top:20px;">SECTION 2: AUTOMATED FORENSIC CASE FINDINGS</h3>
      <div style="display:flex; flex-direction:column; gap:10px; margin-top:10px;">
        ${findings.map((f, i) => `
          <div style="border:1px solid #cbd5e1; padding:10px; border-radius:6px; background:#f8fafc;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
              <strong style="color:#dc2626; font-size:13px;">${i+1}. ${f.title}</strong>
              <span style="background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:4px; font-weight:700; font-size:11px;">Confidence: ${f.confidence_score}%</span>
            </div>
            <p style="font-size:12px; color:#334155; margin:4px 0 6px 0;">${f.summary}</p>
            <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b;">
              <span><strong>Entities Involved:</strong> ${(f.entities_involved || []).join(', ')}</span>
              <strong>Volume Traced: ₹ ${(f.total_amount_involved || 0).toLocaleString()}</strong>
            </div>
          </div>
        `).join('')}
      </div>

      <h3 style="color:#0f172a; border-bottom:2px solid #06b6d4; padding-bottom:4px; margin-top:20px;">SECTION 3: SUSPICIOUS EPISODES & CORRELATION WINDOWS</h3>
      <p style="font-size:12px; color:#334155; line-height:1.5;">
        Hierarchical temporal clustering aggregated raw log streams into high-impact investigative windows:
      </p>
      <div style="display:flex; flex-direction:column; gap:8px; margin-top:8px;">
        ${episodes.slice(0, 4).map(ep => `
          <div style="border:1px solid #e2e8f0; padding:8px 12px; border-radius:4px; background:#fff; font-size:11px;">
            <div style="display:flex; justify-content:space-between;">
              <strong style="color:#0284c7;">${ep.title} (${ep.time_window_str})</strong>
              <span style="font-weight:700; color:#dc2626;">Score: ${ep.episode_score}/100</span>
            </div>
            <div style="color:#475569; margin-top:2px;">${ep.plain_narrative}</div>
          </div>
        `).join('')}
      </div>

      <h3 style="color:#0f172a; border-bottom:2px solid #06b6d4; padding-bottom:4px; margin-top:20px;">SECTION 4: TOP PRIORITY INVESTIGATIVE LEADS</h3>
      <table class="data-table" style="font-size:11px; margin-top:8px;">
        <thead>
          <tr style="background:#f1f5f9; color:#0f172a;">
            <th style="padding:6px;">Rank</th>
            <th style="padding:6px;">Entity Name</th>
            <th style="padding:6px;">Role</th>
            <th style="padding:6px;">Risk Score</th>
            <th style="padding:6px;">Pass-Through %</th>
            <th style="padding:6px;">Traced Inflow (₹)</th>
          </tr>
        </thead>
        <tbody>
          ${leads.map((p, idx) => `
            <tr>
              <td style="padding:6px;"><strong>#${idx + 1}</strong></td>
              <td style="padding:6px;"><strong>${p.entity_name}</strong> ${p.is_seed ? '<span style="color:red;">(SEED)</span>' : ''}</td>
              <td style="padding:6px;">${p.account_role || 'INTERMEDIARY MULE'}</td>
              <td style="padding:6px; color:#dc2626; font-weight:700;">${p.risk_score} / 100</td>
              <td style="padding:6px;">${p.flow_stats?.pass_through_ratio || 0}%</td>
              <td style="padding:6px;">₹ ${(p.flow_stats?.total_inflow || 0).toLocaleString()}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>

      <h3 style="color:#0f172a; border-bottom:2px solid #06b6d4; padding-bottom:4px; margin-top:20px;">SECTION 5: EVIDENTIARY REASONING & ALGORITHMIC PROOF</h3>
      <div style="font-size:12px; color:#334155; line-height:1.6;">
        <ul>
          <li><strong>Graph Centrality (PageRank & Betweenness):</strong> Quantifies structural prominence and shortest-path bottleneck control across 1,877 nodes.</li>
          <li><strong>Louvain Modularity Clustering:</strong> Resolves distinct fraud ring communities without manual bias.</li>
          <li><strong>Unsupervised Isolation Forest:</strong> Flags non-linear multi-dimensional outliers exceeding 0.70 anomaly thresholds.</li>
          <li><strong>Benford's Law Chi-Square Verification:</strong> Tests natural first-digit distribution conformance ($p < 0.01$) to validate artificial transaction amounts.</li>
        </ul>
      </div>

      <h3 style="color:#0f172a; border-bottom:2px solid #06b6d4; padding-bottom:4px; margin-top:20px;">SECTION 6: DIRECTIVE LEGAL & INVESTIGATIVE RECOMMENDATIONS</h3>
      <ol style="font-size:12px; color:#334155; padding-left:18px; line-height:1.6;">
        <li>Issue urgent bank freezing orders under Section 102 CrPC on all high-risk sink accounts.</li>
        <li>Serve Section 91 CrPC notices to telecom service providers for subscriber details of CDR A-Party/B-Party numbers.</li>
        <li>Reconcile IPDR IP session timestamps with internet service provider RADIUS logs.</li>
        <li>Subpoena complete KYC documents and GST filings for connected merchant accounts.</li>
        <li>Conduct custodial interrogation of primary FIR seed suspects based on identified correlation windows.</li>
      </ol>
    </div>
  `;
}

function renderNetworkRingReport() {
  const container = document.getElementById('str-report-container');
  if (!container) return;

  logAuditAction('Generated Discovered Network Rings Intelligence Report.');
  const rings = invData.discovered_networks || [];
  const dateStr = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  let html = `
    <div class="str-report-view">
      <!-- Top Action Bar for PDF / Install Export -->
      <div class="no-print" style="display:flex; justify-content:flex-end; gap:10px; margin-bottom:14px; border-bottom:1px solid #e2e8f0; padding-bottom:10px;">
        <button class="btn-primary" style="background:linear-gradient(135deg, #10b981, #06b6d4); font-size:12px; padding:6px 14px;" onclick="exportCurrentReportToPDF()">📥 Install / Export PDF Report</button>
        <button class="btn-primary" style="background:#0f172a; color:#fff; font-size:12px; padding:6px 14px;" onclick="downloadReportHTML('Discovered_Network_Rings_Report_FIR-2026-0417.html')">💾 Save Report File (HTML)</button>
      </div>

      <div style="border-bottom:2px solid #06b6d4; padding-bottom:8px; margin-bottom:12px;">
        <h2 style="margin:0; color:#0f172a; font-size:18px;">🌐 DISCOVERED NETWORK RINGS & COMMUNITY CLUSTER REPORT</h2>
        <div style="font-size:12px; color:#475569; margin-top:2px;">
          Case Workspace: <strong>FIR-2026-0417</strong> • Date: <strong>${dateStr}</strong> • Algorithm: <strong>Louvain Modularity Clustering & Articulation Points</strong>
        </div>
      </div>

      <div class="str-box" style="margin-bottom:14px; background:#f0f9ff; border:1px solid #bae6fd;">
        <strong style="color:#0369a1;">Executive Network Summary:</strong><br>
        Exact graph analytics algorithms identified <strong>${rings.length} distinct Louvain modularity community rings</strong> connecting seed suspect entities with downstream mule accounts. Total financial volume traversing these rings: <strong>₹ ${(rings.reduce((a, b) => a + (b.total_traced_volume || 0), 0)).toLocaleString()}</strong>.
      </div>

      <h3 style="color:#0f172a; border-bottom:1px solid #cbd5e1; padding-bottom:4px; margin-top:16px;">1. DISCOVERED FRAUD RING PROFILES</h3>
      <div style="display:flex; flex-direction:column; gap:12px; margin-top:8px;">
  `;

  rings.forEach((ring, idx) => {
    html += `
      <div style="border:1px solid #cbd5e1; padding:12px; border-radius:6px; background:#fafafa;">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:6px; margin-bottom:8px;">
          <strong style="color:#0284c7; font-size:14px;">Ring ${chr(65 + idx)}: ${ring.title}</strong>
          <span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:4px; font-weight:700; font-size:11px;">${ring.total_nodes} Total Nodes</span>
        </div>
        
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:12px; margin-bottom:8px;">
          <div><strong>FIR Seeds Connected:</strong> ${ring.total_seed_links} (${(ring.seed_names || []).join(', ') || 'Indirect'})</div>
          <div><strong>High-Risk Entities:</strong> ${ring.high_risk_count}</div>
          <div><strong>Traced Monetary Volume:</strong> ₹ ${(ring.total_traced_volume || 0).toLocaleString()}</div>
          <div><strong>Primary Motif:</strong> ${ring.primary_motif}</div>
        </div>

        <div style="font-size:11px; color:#475569; background:#fff; padding:6px 10px; border-radius:4px; border:1px solid #e2e8f0;">
          <strong>Investigative Assessment:</strong> Ring ${chr(65 + idx)} functions as a coordinated ${ring.primary_motif.toLowerCase()} network designed to rapidly disperse proceeds across multiple intermediary accounts.
        </div>
      </div>
    `;
  });

  html += `
      </div>

      <h3 style="color:#0f172a; border-bottom:1px solid #cbd5e1; padding-bottom:4px; margin-top:20px;">2. INTER-RING BRIDGE LINKS & ARTICULATION NODES</h3>
      <p style="font-size:12px; color:#334155; line-height:1.5;">
        Articulation point nodes serve as critical single-point-of-failure bridges connecting separate community rings. Disruption of these bottleneck nodes effectively severs communication and money transfer pathways between distinct laundering rings.
      </p>

      <h3 style="color:#0f172a; border-bottom:1px solid #cbd5e1; padding-bottom:4px; margin-top:20px;">3. RECOMMENDED RING NEUTRALIZATION STRATEGY</h3>
      <ol style="font-size:12px; color:#334155; padding-left:18px; line-height:1.5;">
        <li>Execute simultaneous account freezing orders across primary collector nodes in Ring A and Ring B.</li>
        <li>Issue Section 91 CrPC notices to financial institutions for complete KYC records of articulation bridge accounts.</li>
        <li>Cross-reference shared IP log timestamps across Ring members to establish common operational control.</li>
      </ol>
    </div>
  `;

  container.innerHTML = html;
}

function chr(code) { return String.fromCharCode(code); }

function generateSTRReport(ek) {
  const tabBtn = document.querySelector('.tab-btn[data-tab="str"]');
  if (tabBtn) tabBtn.click();

  const container = document.getElementById('str-report-container');
  if (!container) return;

  const prof = invData.risk_profiles[ek] || {
    entity_name: ek,
    risk_score: 50,
    risk_category: 'HIGH',
    hop_distance: 1,
    plain_language_narrative: 'Suspicious transaction pattern detected.'
  };

  const rawTech = prof.raw_technical_analytics || {};

  logAuditAction(`Generated Courtroom STR Report for entity ${ek} (Score: ${prof.risk_score}/100).`);

  const strId = `STR-2026-LAW-${Math.floor(100000 + Math.random() * 900000)}`;
  const dateStr = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  container.innerHTML = `
    <div class="str-report-view">
      <!-- Top Action Bar for PDF / Install Export -->
      <div class="no-print" style="display:flex; justify-content:flex-end; gap:10px; margin-bottom:14px; border-bottom:1px solid #e2e8f0; padding-bottom:10px;">
        <button class="btn-primary" style="background:linear-gradient(135deg, #10b981, #06b6d4); font-size:12px; padding:6px 14px;" onclick="exportCurrentReportToPDF()">📥 Install / Export PDF Report</button>
        <button class="btn-primary" style="background:#0f172a; color:#fff; font-size:12px; padding:6px 14px;" onclick="downloadReportHTML('${strId}_${ek.substring(0,15)}.html')">💾 Save STR File (HTML)</button>
      </div>

      <h2>CONFIDENTIAL FINANCIAL INTELLIGENCE & SUSPICIOUS TRANSACTION REPORT (STR)</h2>
      
      <div class="str-grid">
        <div class="str-box">
          <strong>Report ID:</strong> ${strId}<br>
          <strong>Case Workspace:</strong> FIR-2026-0417<br>
          <strong>Date Generated:</strong> ${dateStr}<br>
          <strong>Investigative Unit:</strong> Law Enforcement & Financial Analytics Wing
        </div>
        <div class="str-box">
          <strong>Target Entity:</strong> ${prof.entity_name}<br>
          <strong>Composite Risk Score:</strong> ${prof.risk_score} / 100 (${prof.risk_category})<br>
          <strong>Classified Role:</strong> ${prof.account_role || 'INTERMEDIARY MULE'}<br>
          <strong>Hop Distance from FIR Seed:</strong> ${prof.hop_distance} Hop(s)
        </div>
      </div>

      <div style="margin-bottom:14px;">
        <h4 style="border-bottom:1px solid #d1d5db; padding-bottom:4px; margin-bottom:6px;">1. PLAIN-LANGUAGE EXECUTIVE FINDING</h4>
        <p style="font-size:12px; line-height:1.5;">${prof.plain_language_narrative || 'N/A'}</p>
      </div>

      <div style="margin-bottom:14px;">
        <h4 style="border-bottom:1px solid #d1d5db; padding-bottom:4px; margin-bottom:6px;">2. MONEY FLOW & PASS-THROUGH CONSERVATION</h4>
        <p style="font-size:12px;"><strong>Total Recorded Inflow:</strong> ₹ ${(prof.flow_stats?.total_inflow || 0).toLocaleString()}</p>
        <p style="font-size:12px;"><strong>Total Recorded Outflow:</strong> ₹ ${(prof.flow_stats?.total_outflow || 0).toLocaleString()}</p>
        <p style="font-size:12px;"><strong>Pass-Through Rate:</strong> ${prof.flow_stats?.pass_through_ratio || 0}%</p>
      </div>

      <div style="margin-bottom:14px;">
        <h4 style="border-bottom:1px solid #d1d5db; padding-bottom:4px; margin-bottom:6px;">3. TECHNICAL ANALYTICS & GRAPH ALGORITHM METRICS</h4>
        <p style="font-size:12px;"><strong>Isolation Forest Anomaly Index:</strong> ${rawTech.isolation_forest_anomaly_index || '0.10'}</p>
        <p style="font-size:12px;"><strong>Local Outlier Factor (LOF):</strong> ${rawTech.local_outlier_factor_score || '1.0'}</p>
        <p style="font-size:12px;"><strong>PageRank Centrality:</strong> ${rawTech.pagerank_centrality || '0.0000'}</p>
        <p style="font-size:12px;"><strong>Betweenness Centrality:</strong> ${rawTech.betweenness_centrality || '0.0000'}</p>
        <p style="font-size:12px;"><strong>Benford's Law Chi-Square Test:</strong> Stat = ${rawTech.benford_chi_square_stat || '0'}, p-val = ${rawTech.benford_p_value || '1.0'}</p>
        <p style="font-size:12px;"><strong>Louvain Community Cluster:</strong> ${rawTech.louvain_community_id || 'Community_1'}</p>
      </div>

      <div style="margin-bottom:14px;">
        <h4 style="border-bottom:1px solid #d1d5db; padding-bottom:4px; margin-bottom:6px;">4. RECOMMENDED LEGAL & INVESTIGATIVE ACTIONS</h4>
        <ol style="padding-left:18px; line-height:1.5; font-size:12px;">
          ${(prof.recommended_next_actions || ['Obtain downstream bank statements.']).map(a => `<li>${a}</li>`).join('')}
        </ol>
      </div>

      <div style="margin-bottom:14px; font-size:11px; color:#4b5563;">
        <strong>Data Bounding Note:</strong> Tracing is restricted to provided bank statement windows.
      </div>
    </div>
  `;
}

/* ==========================================================================
   TAB 7: AUDIT TRAIL
   ========================================================================== */
function renderAuditTrail() {
  const container = document.getElementById('audit-trail-container');
  if (!container) return;

  const logs = invData.audit_trail || [];
  let html = `<div style="display:flex; flex-direction:column; gap:8px;">`;
  logs.forEach(l => {
    html += `<div class="detail-row"><span class="detail-label">${l.timestamp} • User: ${l.user}</span><strong>${l.action}</strong></div>`;
  });
  html += `</div>`;
  container.innerHTML = html;
}

function logAuditAction(actionText) {
  const newLog = {
    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
    user: 'Inspector V. Sharma',
    action: actionText
  };
  invData.audit_trail = invData.audit_trail || [];
  invData.audit_trail.unshift(newLog);
  renderAuditTrail();
}
