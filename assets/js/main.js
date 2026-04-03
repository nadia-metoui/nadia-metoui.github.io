---
# This empty front matter tells Jekyll to process this file!
---

// ── CONFIGURATION ────────────────────────────────────────────────────────
const ORCID_ID = '0000-0001-6690-2937';
const ORCID_API = `https://pub.orcid.org/v3.0/${ORCID_ID}`;

/**
 * JEKYLL DATA INJECTION
 */
const FALLBACK_PUBS = {{ site.data.publications | jsonify }};

// ── HELPERS ──────────────────────────────────────────────────────────────
function orcidTypeToLocal(workType) {
    const journals = ['journal-article', 'book-chapter', 'book', 'report'];
    const talks = ['conference-abstract', 'lecture-speech', 'other'];
    if (journals.includes(workType)) return 'journal';
    if (talks.includes(workType)) return 'talk';
    return 'conference';
}

function badgeFromType(type, workType) {
    if (type === 'journal') return 'Journal';
    if (type === 'talk') return workType === 'conference-abstract' ? 'Abstract' : 'Talk';
    return 'Conference';
}

function buildPubHTML(pub, idx) {
    const num = typeof idx === 'number' ? idx + 1 : '★';
    const titleEl = pub.url
        ? `<a href="${pub.url}" target="_blank" rel="noopener">${pub.title}</a>`
        : pub.title;
    
    return `
      <div class="pub-item" data-type="${pub.type}">
        <div class="pub-idx">${num}</div>
        <div class="pub-body">
          <span class="pub-badge">${pub.badge}</span>
          <div class="pub-title">${titleEl}</div>
          ${pub.authors ? `<div class="pub-authors">${pub.authors}</div>` : ''}
          ${pub.venue ? `<div class="pub-venue">${pub.venue}</div>` : ''}
          ${pub.year ? `<div class="pub-year">${pub.year}</div>` : ''}
        </div>
      </div>`;
}

function renderPubs(pubs) {
    const list = document.getElementById('pub-list');
    if (!list) return;

    const numbered = pubs.filter(p => p.type !== 'talk');
    const talks = pubs.filter(p => p.type === 'talk');

    list.innerHTML =
        numbered.map((p, i) => buildPubHTML(p, i)).join('') +
        talks.map(p => buildPubHTML(p, '★')).join('');
}

// ── CORE LOGIC ───────────────────────────────────────────────────────────
async function loadOrcidPubs() {
    const status = document.getElementById('orcid-status');
    if (status) status.textContent = 'Syncing with ORCID...';
    
    try {
        const res = await fetch(`${ORCID_API}/works`, {
            headers: { 'Accept': 'application/json' }
        });
        if (!res.ok) throw new Error('ORCID API Unreachable');
        
        const data = await res.json();
        const groups = data.group || [];

        if (groups.length === 0) {
            renderPubs(FALLBACK_PUBS);
            return;
        }

        const works = await Promise.all(groups.map(async g => {
            const summary = g['work-summary'][0];
            const putCode = summary['put-code'];
            let url = '';
            
            try {
                const detail = await fetch(`${ORCID_API}/work/${putCode}`, {
                    headers: { 'Accept': 'application/json' }
                });
                if (detail.ok) {
                    const d = await detail.json();
                    const ids = d['external-ids']?.['external-id'] || [];
                    const doi = ids.find(x => x['external-id-type'] === 'doi');
                    if (doi) url = `https://doi.org/${doi['external-id-value']}`;
                }
            } catch (e) {}

            const workType = summary.type || '';
            const type = orcidTypeToLocal(workType);
            
            return {
                type: type,
                badge: badgeFromType(type, workType),
                title: summary.title?.title?.value || 'Untitled',
                url: url,
                authors: '', 
                venue: summary['journal-title']?.value || '',
                year: summary['publication-date']?.year?.value || ''
            };
        }));

        works.sort((a, b) => (parseInt(b.year) || 0) - (parseInt(a.year) || 0));
        renderPubs(works);
        if (status) {
            status.textContent = `Updated from ORCID · ${works.length} works`;
            status.style.color = 'var(--accent)';
        }

    } catch (err) {
        renderPubs(FALLBACK_PUBS);
        if (status) {
            status.textContent = 'Showing saved publications';
            status.style.color = 'var(--ink-faint)';
        }
    }
}

// ── UI EVENTS ─────────────────────────────────────────────────────────────
window.filterPubs = function(type, btn) {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.pub-item').forEach(item => {
        item.style.display = (type === 'all' || item.dataset.type === type) ? 'flex' : 'none';
    });
};

window.addEventListener('scroll', () => {
    const sectionEls = document.querySelectorAll('section[id]');
    const navAs = document.querySelectorAll('.nav-links a');
    let cur = '';
    sectionEls.forEach(s => { if (window.scrollY >= s.offsetTop - 110) cur = s.id; });
    navAs.forEach(a => {
        a.classList.toggle('active', a.getAttribute('href') === '#' + cur);
    });
});

// Initialize
document.addEventListener('DOMContentLoaded', loadOrcidPubs);