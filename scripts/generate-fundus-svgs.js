const fs = require('fs');
const path = require('path');

const publicDir = path.join(__dirname, '..', 'public');
if (!fs.existsSync(publicDir)) {
  fs.mkdirSync(publicDir, { recursive: true });
}

// Function to generate rich realistic fundus SVG
function generateFundusSVG({
  type = 'normal', // 'normal' | 'moderate' | 'severe' | 'mild' | 'ungradeable'
  width = 800,
  height = 800,
  isWide = false,
}) {
  const cx = isWide ? width / 2 : 400;
  const cy = height / 2;
  const radius = isWide ? Math.min(width, height) * 0.46 : 370;

  // Optic disc at nasal side (e.g. x = 270, y = 390 for right eye)
  const discX = isWide ? width * 0.35 : 270;
  const discY = cy;
  // Fovea at temporal side (e.g. x = 490, y = 410)
  const foveaX = isWide ? width * 0.6 : 490;
  const foveaY = cy + 15;

  let pathologies = '';
  let blurFilter = '';
  let opacity = 1.0;

  if (type === 'ungradeable') {
    blurFilter = `
      <filter id="severeBlur">
        <feGaussianBlur stdDeviation="16" />
      </filter>
    `;
    opacity = 0.55;
  }

  // Pathologies for DR
  if (type === 'moderate' || type === 'severe' || type === 'mild') {
    // Microaneurysms (tiny crimson dots)
    const maCoords =
      type === 'mild'
        ? [[460, 360], [480, 440], [520, 390]]
        : type === 'moderate'
        ? [
            [450, 350], [465, 335], [510, 340], [530, 380], [545, 430],
            [480, 470], [440, 460], [420, 380], [515, 460], [475, 490],
            [560, 410], [430, 340], [500, 320], [390, 430], [510, 495]
          ]
        : [
            // severe: many
            [410, 310], [440, 330], [470, 320], [510, 315], [540, 340],
            [560, 370], [570, 420], [550, 460], [520, 490], [480, 510],
            [430, 490], [400, 460], [380, 420], [370, 370], [490, 340],
            [530, 410], [460, 460], [420, 360], [500, 470], [540, 440]
          ];

    maCoords.forEach(([x, y]) => {
      pathologies += `<circle cx="${x}" cy="${y}" r="2.8" fill="#880e0e" stroke="#ff2222" stroke-width="0.8" />`;
    });

    // Hard Exudates (bright yellowish lipid clusters)
    if (type === 'moderate' || type === 'severe') {
      const heClusters = [
        [510, 390], [518, 395], [514, 403], [525, 392], [522, 408],
        [470, 430], [476, 435], [468, 440], [482, 438],
        [535, 360], [542, 365], [540, 355]
      ];
      heClusters.forEach(([x, y]) => {
        pathologies += `<circle cx="${x}" cy="${y}" r="${Math.random() * 2.5 + 2}" fill="#ffeb3b" opacity="0.92" />`;
      });
    }

    // Hemorrhages (dark irregular blot patches)
    if (type === 'moderate' || type === 'severe') {
      const blotHem =
        type === 'moderate'
          ? [
              [430, 420, 6, 4], [530, 450, 7, 5], [480, 330, 5, 4]
            ]
          : [
              [420, 430, 11, 7], [530, 460, 12, 8], [470, 320, 9, 6],
              [360, 340, 14, 8], [560, 330, 10, 7], [400, 520, 12, 9],
              [340, 440, 15, 10], [520, 530, 14, 8]
            ];

      blotHem.forEach(([x, y, rx, ry]) => {
        pathologies += `<ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" fill="#4a0404" opacity="0.88" />`;
      });
    }

    // Cotton wool spots in severe
    if (type === 'severe') {
      const cws = [[440, 360], [520, 360], [460, 470]];
      cws.forEach(([x, y]) => {
        pathologies += `<ellipse cx="${x}" cy="${y}" rx="14" ry="9" fill="#ffffff" opacity="0.65" filter="blur(2px)" />`;
      });
    }
  }

  // Ungradeable artifacts
  let glareArtifact = '';
  if (type === 'ungradeable') {
    glareArtifact = `
      <!-- Dense Cataract Haze and Glare Flare -->
      <circle cx="${cx - 50}" cy="${cy - 80}" r="220" fill="url(#glareGrad)" opacity="0.75" />
      <path d="M 100 200 Q 300 150 500 260 Q 350 400 100 200 Z" fill="#ffffff" opacity="0.55" filter="blur(8px)" />
    `;
  }

  return `
<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <!-- Choroid Deep Vascular Gradients -->
    <radialGradient id="fundusGrad_${type}" cx="45%" cy="48%" r="52%">
      <stop offset="0%" stop-color="#dd5826" />
      <stop offset="45%" stop-color="#c43f18" />
      <stop offset="75%" stop-color="#9a290d" />
      <stop offset="95%" stop-color="#5a1405" />
      <stop offset="100%" stop-color="#1a0401" />
    </radialGradient>

    <!-- Optic Disc Gradient -->
    <radialGradient id="discGrad" cx="45%" cy="45%" r="50%">
      <stop offset="0%" stop-color="#fff2c2" />
      <stop offset="65%" stop-color="#f8c878" />
      <stop offset="90%" stop-color="#e09540" />
      <stop offset="100%" stop-color="#b85b20" />
    </radialGradient>

    <!-- Fovea Avascular Zone Gradient -->
    <radialGradient id="foveaGrad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#5e1507" stop-opacity="0.95" />
      <stop offset="60%" stop-color="#7c1e0b" stop-opacity="0.6" />
      <stop offset="100%" stop-color="#c43f18" stop-opacity="0" />
    </radialGradient>

    <!-- Glare Gradient for ungradeable -->
    <radialGradient id="glareGrad" cx="30%" cy="30%" r="70%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.9" />
      <stop offset="50%" stop-color="#ffeedd" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
    </radialGradient>

    ${blurFilter}

    <clipPath id="fundusAperture_${type}">
      ${
        isWide
          ? `<rect x="0" y="0" width="${width}" height="${height}" rx="28" />`
          : `<circle cx="${cx}" cy="${cy}" r="${radius}" />`
      }
    </clipPath>
  </defs>

  <g clip-path="url(#fundusAperture_${type})" opacity="${opacity}">
    <!-- Background Retinal Canvas -->
    <rect x="0" y="0" width="${width}" height="${height}" fill="#0d0402" />
    <circle cx="${cx}" cy="${cy}" r="${isWide ? width * 0.7 : radius + 20}" fill="url(#fundusGrad_${type})" ${type === 'ungradeable' ? 'filter="url(#severeBlur)"' : ''} />

    <!-- Subtle Choroidal Pigment Mottling Texture -->
    <g opacity="0.18">
      <circle cx="${cx + 80}" cy="${cy - 120}" r="160" fill="#751b08" />
      <circle cx="${cx - 110}" cy="${cy + 90}" r="190" fill="#541205" />
      <circle cx="${cx + 140}" cy="${cy + 80}" r="170" fill="#661706" />
    </g>

    <!-- Fovea Avascular Zone (Macula Center) -->
    <circle cx="${foveaX}" cy="${foveaY}" r="45" fill="url(#foveaGrad)" />
    <!-- Foveal light reflex -->
    <circle cx="${foveaX}" cy="${foveaY}" r="3" fill="#ffddaa" opacity="0.65" />

    <!-- Optic Disc -->
    <ellipse cx="${discX}" cy="${discY}" rx="38" ry="46" fill="url(#discGrad)" />
    <!-- Physiological Cup -->
    <ellipse cx="${discX - 4}" cy="${discY}" rx="18" ry="22" fill="#fffbe6" opacity="0.85" />

    <!-- Primary Retinal Vascular Tree (Arterioles & Venules) -->
    <g stroke-linecap="round" stroke-linejoin="round" ${type === 'ungradeable' ? 'filter="url(#severeBlur)"' : ''}>
      <!-- Superior Temporal Venous Arcade (Deep Red, Thicker) -->
      <path d="M ${discX} ${discY - 15} C ${discX + 40} ${discY - 110}, ${discX + 130} ${discY - 170}, ${foveaX + 80} ${cy - 180} C ${foveaX + 160} ${cy - 190}, ${width - 80} ${cy - 150}, ${width - 30} ${cy - 110}" stroke="#520904" stroke-width="5.5" fill="none" opacity="0.9" />
      <!-- Superior Temporal Arteriole (Brighter Red, Thinner, A/V pair) -->
      <path d="M ${discX + 5} ${discY - 18} C ${discX + 48} ${discY - 105}, ${discX + 138} ${discY - 160}, ${foveaX + 90} ${cy - 170} C ${foveaX + 150} ${cy - 175}, ${width - 90} ${cy - 135}, ${width - 40} ${cy - 95}" stroke="#9e1e0a" stroke-width="3.2" fill="none" opacity="0.95" />

      <!-- Inferior Temporal Venous Arcade -->
      <path d="M ${discX} ${discY + 15} C ${discX + 50} ${discY + 115}, ${discX + 140} ${discY + 175}, ${foveaX + 90} ${cy + 190} C ${foveaX + 170} ${cy + 200}, ${width - 70} ${cy + 160}, ${width - 20} ${cy + 110}" stroke="#520904" stroke-width="5.5" fill="none" opacity="0.9" />
      <!-- Inferior Temporal Arteriole -->
      <path d="M ${discX + 5} ${discY + 18} C ${discX + 58} ${discY + 110}, ${discX + 148} ${discY + 165}, ${foveaX + 100} ${cy + 178} C ${foveaX + 160} ${cy + 185}, ${width - 80} ${cy + 145}, ${width - 30} ${cy + 95}" stroke="#9e1e0a" stroke-width="3.2" fill="none" opacity="0.95" />

      <!-- Superior Nasal Vessels -->
      <path d="M ${discX - 8} ${discY - 15} C ${discX - 50} ${discY - 100}, ${discX - 100} ${discY - 160}, 50 ${cy - 160}" stroke="#520904" stroke-width="4.5" fill="none" opacity="0.88" />
      <path d="M ${discX - 4} ${discY - 18} C ${discX - 44} ${discY - 95}, ${discX - 92} ${discY - 150}, 60 ${cy - 150}" stroke="#9e1e0a" stroke-width="2.8" fill="none" opacity="0.95" />

      <!-- Inferior Nasal Vessels -->
      <path d="M ${discX - 8} ${discY + 15} C ${discX - 50} ${discY + 100}, ${discX - 100} ${discY + 160}, 50 ${cy + 160}" stroke="#520904" stroke-width="4.5" fill="none" opacity="0.88" />
      <path d="M ${discX - 4} ${discY + 18} C ${discX - 44} ${discY + 95}, ${discX - 92} ${discY + 150}, 60 ${cy + 150}" stroke="#9e1e0a" stroke-width="2.8" fill="none" opacity="0.95" />

      <!-- Microvascular Secondary Branches toward Macula -->
      <path d="M ${discX + 70} ${discY - 80} C ${discX + 120} ${discY - 70}, ${foveaX - 30} ${foveaY - 50}, ${foveaX} ${foveaY - 35}" stroke="#8c1c0a" stroke-width="1.8" fill="none" opacity="0.75" />
      <path d="M ${discX + 80} ${discY + 80} C ${discX + 130} ${discY + 70}, ${foveaX - 30} ${foveaY + 50}, ${foveaX} ${foveaY + 35}" stroke="#8c1c0a" stroke-width="1.8" fill="none" opacity="0.75" />
    </g>

    <!-- Pathologies (Microaneurysms, Exudates, Hemorrhages) -->
    <g>
      ${pathologies}
    </g>

    ${glareArtifact}
  </g>

  <!-- Precision Aperture Outer Ring -->
  ${
    !isWide
      ? `<circle cx="${cx}" cy="${cy}" r="${radius}" stroke="#262a30" stroke-width="3" fill="none" />`
      : ''
  }
</svg>
`;
}

// Generate all SVG files
const svgs = [
  { name: 'retina-moderate-npdr.svg', type: 'moderate', width: 800, height: 800 },
  { name: 'retina-normal.svg', type: 'normal', width: 800, height: 800 },
  { name: 'retina-severe-npdr.svg', type: 'severe', width: 800, height: 800 },
  { name: 'retina-mild-npdr.svg', type: 'mild', width: 800, height: 800 },
  { name: 'retina-ungradeable.svg', type: 'ungradeable', width: 800, height: 800 },
  { name: 'fundus-hero-banner.svg', type: 'moderate', width: 1400, height: 500, isWide: true },
];

svgs.forEach((item) => {
  const content = generateFundusSVG(item);
  fs.writeFileSync(path.join(publicDir, item.name), content.trim());
  console.log('Created ' + item.name);
});
