// Design Tokens extracted from Figma Design System + eGain Brand Manual 2026
// Prism Eval by eGain

export const colors = {
  // Primary palette (eGain Brand Magenta — #b91d8f anchored at 600)
  primary: {
    '50': '#FDF2FA',
    '100': '#FCE7F5',
    '200': '#FACFEC',
    '300': '#F7A8DC',
    '400': '#F272C3',
    '500': '#D93DA6',
    '600': '#B91D8F',
    '700': '#9A1677',
    '800': '#7E1461',
    '900': '#68124F',
  },
  // eGain official secondary colors — soft pastels from brand guide 2026
  // Use as background tints to complement eGain Magenta
  secondary: {
    pink: '#FEF0FD',       // eGain Pink — near-white magenta tint
    ochre: '#F8DC8B',      // Light Ochre
    blue: '#E9F6FD',       // Light Blue
    purple: '#EFECFF',     // Light Purple
    turquoise: '#E6F6F8',  // Light Turquoise
    yellow: '#FFFCDF',     // Light Yellow
  },
  // Neutral palette
  neutral: {
    '0': '#FFFFFF',
    '50': '#F9FAFB',
    '100': '#F3F4F6',
    '200': '#E5E7EB',
    '300': '#D1D5DB',
    '400': '#9CA3AF',
    '500': '#6B7280',
    '600': '#4B5563',
    '700': '#374151',
    '800': '#1F2937',
    '900': '#111827',
  },
  // Background colors
  background: {
    primary: '#FFFFFF',
    secondary: '#F9FAFB',
    tertiary: '#F3F4F6',
    inverse: '#111827',
    brandSubtle: '#FEF0FD',   // eGain Pink (brand guide 2026)
    brandMuted: '#FCE7F5',
    successSubtle: '#F0FDF4',
    successMuted: '#DCFCE7',
    warningSubtle: '#FFFBEB',
    warningMuted: '#FEF3C7',
    errorSubtle: '#FEF2F2',
    errorMuted: '#FEE2E2',
    infoSubtle: '#EFF6FF',
    infoMuted: '#DBEAFE',
    overlay: 'rgba(0, 0, 0, 0.5)',
  },
  // Text colors
  text: {
    primary: '#111827',
    secondary: '#4B5563',
    tertiary: '#6B7280',
    disabled: '#9CA3AF',
    inverse: '#FFFFFF',
    brand: '#B91D8F',
    success: '#16A34A',
    warning: '#D97706',
    error: '#DC2626',
    info: '#2563EB',
    link: '#B91D8F',
    linkHover: '#9A1677',
  },
  // Icon colors
  icon: {
    primary: '#374151',
    secondary: '#6B7280',
    tertiary: '#9CA3AF',
    disabled: '#D1D5DB',
    inverse: '#FFFFFF',
    brand: '#B91D8F',
    success: '#16A34A',
    successLight: '#4ADE80',  // green-400 — confirmation/check icons on dark surfaces
    warning: '#D97706',
    error: '#DC2626',
    info: '#2563EB',
  },
  // Border colors
  border: {
    primary: '#E5E7EB',
    secondary: '#D1D5DB',
    tertiary: '#F3F4F6',
    focus: '#B91D8F',
    error: '#DC2626',
    success: '#16A34A',
    warning: '#D97706',
    warningMuted: '#FDE68A',  // amber-200 — notice bar / inline alert border
    info: '#2563EB',
    brand: '#B91D8F',
  },
  // Brand aliases — shorthand tokens for Tailwind classes
  // Use these in components instead of primary-600/50/700
  brand: {
    DEFAULT: '#B91D8F',   // eGain Magenta — buttons, active text, links, focus rings
    pink: '#FEF0FD',      // eGain Pink — subtle brand surfaces, hover backgrounds
    light: '#FDF2FA',     // primary-50  — active backgrounds
    hover: '#9A1677',     // primary-700 — hover states on brand buttons
    black: '#000000',     // brand black
    white: '#FFFFFF',     // brand white
    // Print reference: eGain Magenta Pantone equivalent (brand guide 2026)
    pantone: '18-2336 TCX Very Berry',
  },
};

export const fontFamilies = {
  // Primary typeface per eGain Brand Manual 2026 — Helvetica Neue Pro
  sans: '"Helvetica Neue", Helvetica, Arial, -apple-system, BlinkMacSystemFont, sans-serif',
  // Secondary typeface — Aileron (for presentation slides only; requires design team review for other uses)
  secondary: 'Aileron, "Helvetica Neue", Helvetica, Arial, sans-serif',
  mono: '"JetBrains Mono", "Fira Code", Consolas, monospace',
};

export const fontSizes = {
  '3xs': '0.625rem',  // 10px — micro labels (e.g. run limit label)
  '2xs': '0.6875rem', // 11px — sublabels, helper text, optional tags
  xs: '0.75rem',    // 12px
  sm: '0.875rem',   // 14px
  base: '1rem',     // 16px
  lg: '1.125rem',   // 18px
  xl: '1.25rem',    // 20px
  '2xl': '1.5rem',  // 24px
  '3xl': '1.875rem', // 30px
  '4xl': '2.25rem', // 36px
  '5xl': '3rem',    // 48px
};

export const fontWeights = {
  // Aligned to Helvetica Neue Pro weights from eGain Brand Manual 2026
  ultraLight: '200',  // HN 25 Ultra Light
  thin: '300',        // HN 35 Thin — web maps to 300 (same as light; visually distinct in the Pro typeface)
  light: '300',       // HN 45 Light
  normal: '400',      // HN 55 Roman
  medium: '500',      // HN 65 Medium
  semibold: '600',
  bold: '700',        // HN 75 Bold
  // Secondary typeface (Aileron) only:
  black: '900',       // Aileron Black — do not use with Helvetica Neue Pro
};

export const lineHeights = {
  none: '1',
  tight: '1.25',
  snug: '1.375',
  normal: '1.5',
  relaxed: '1.625',
  loose: '2',
};

export const typography = {
  'display-lg': {
    fontFamily: fontFamilies.sans,
    fontSize: '2.25rem',    // 36px — hero headings
    fontWeight: '700',
    lineHeight: '1.25',
    letterSpacing: '-0.025em',
  },
  'display-md': {
    fontFamily: fontFamilies.sans,
    fontSize: '1.875rem',   // 30px — page titles
    fontWeight: '700',
    lineHeight: '1.25',
    letterSpacing: '-0.025em',
  },
  'display-sm': {
    fontFamily: fontFamilies.sans,
    fontSize: '1.5rem',     // 24px — section titles
    fontWeight: '600',
    lineHeight: '1.375',
  },
  'heading-lg': {
    fontFamily: fontFamilies.sans,
    fontSize: '1.25rem',    // 20px — card headings
    fontWeight: '600',
    lineHeight: '1.375',
  },
  'heading-md': {
    fontFamily: fontFamilies.sans,
    fontSize: '1.125rem',   // 18px — sub-headings
    fontWeight: '600',
    lineHeight: '1.5',
  },
  'heading-sm': {
    fontFamily: fontFamilies.sans,
    fontSize: '1rem',       // 16px — small headings, header title
    fontWeight: '600',
    lineHeight: '1.5',
  },
  'body-lg': {
    fontFamily: fontFamilies.sans,
    fontSize: '1rem',       // 16px — large body text
    fontWeight: '400',
    lineHeight: '1.625',
  },
  'body-md': {
    fontFamily: fontFamilies.sans,
    fontSize: '0.875rem',   // 14px — default body text
    fontWeight: '400',
    lineHeight: '1.5',
  },
  'body-sm': {
    fontFamily: fontFamilies.sans,
    fontSize: '0.8125rem',  // 13px — sidebar items, small body
    fontWeight: '400',
    lineHeight: '1.5',
  },
  'label-lg': {
    fontFamily: fontFamilies.sans,
    fontSize: '1rem',       // 16px — large labels
    fontWeight: '500',
    lineHeight: '1.5',
  },
  'label-md': {
    fontFamily: fontFamilies.sans,
    fontSize: '0.875rem',   // 14px — default labels, horizontal tabs
    fontWeight: '500',
    lineHeight: '1.5',
  },
  'label-sm': {
    fontFamily: fontFamilies.sans,
    fontSize: '0.75rem',    // 12px — small labels, section headers
    fontWeight: '500',
    lineHeight: '1.5',
  },
  caption: {
    fontFamily: fontFamilies.sans,
    fontSize: '0.75rem',    // 12px — captions, footnotes, badges
    fontWeight: '400',
    lineHeight: '1.5',
  },
  code: {
    fontFamily: fontFamilies.mono,
    fontSize: '0.875rem',   // 14px — code / monospace
    fontWeight: '400',
    lineHeight: '1.5',
  },
};

export const spacing = {
  px: '1px',
  '0': '0',
  '0.5': '0.125rem',
  '1': '0.25rem',
  '1.5': '0.375rem',
  '2': '0.5rem',
  '2.5': '0.625rem',
  '3': '0.75rem',
  '3.5': '0.875rem',
  '4': '1rem',
  '5': '1.25rem',
  '6': '1.5rem',
  '7': '1.75rem',
  '8': '2rem',
  '9': '2.25rem',
  '10': '2.5rem',
  '11': '2.75rem',
  '12': '3rem',
  '14': '3.5rem',
  '16': '4rem',
  '20': '5rem',
  '24': '6rem',
  '28': '7rem',
  '32': '8rem',
  '36': '9rem',
  '40': '10rem',
  '44': '11rem',
  '48': '12rem',
  '52': '13rem',
  '56': '14rem',
  '60': '15rem',
  '64': '16rem',
  '72': '18rem',
  '80': '20rem',
  '96': '24rem',
};

export const space = {
  gap: {
    none: '0',
    xxs: '0.25rem',
    xs: '0.5rem',
    sm: '0.75rem',
    md: '1rem',
    lg: '1.5rem',
    xl: '2rem',
    '2xl': '3rem',
    '3xl': '4rem',
  },
  padding: {
    none: '0',
    xxs: '0.25rem',
    xs: '0.5rem',
    sm: '0.75rem',
    md: '1rem',
    lg: '1.5rem',
    xl: '2rem',
    '2xl': '3rem',
    '3xl': '4rem',
  },
  component: {
    xs: '0.5rem',
    sm: '0.75rem',
    md: '1rem',
    lg: '1.25rem',
    xl: '1.5rem',
  },
  section: {
    sm: '2rem',
    md: '3rem',
    lg: '4rem',
    xl: '6rem',
  },
};

export const borderRadius = {
  none: '0',
  sm: '0.125rem',
  DEFAULT: '0.25rem',
  md: '0.375rem',
  lg: '0.5rem',
  xl: '0.75rem',
  '2xl': '1rem',
  '3xl': '1.5rem',
  full: '9999px',
};

export const shadows = {
  none: 'none',
  sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  DEFAULT: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  xl: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  '2xl': '0 25px 50px -12px rgb(0 0 0 / 0.25)',
  inner: 'inset 0 2px 4px 0 rgb(0 0 0 / 0.05)',
  'inner-md': 'inset 0 4px 6px 0 rgb(0 0 0 / 0.1)',
};

export const elevation = {
  card: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  dropdown: '0 4px 12px rgba(0,0,0,0.1)',
  toast: '0 4px 12px rgba(0,0,0,0.18)',
  modal: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  popover: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  tooltip: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
};

export const blur = {
  none: '0',
  sm: '4px',
  DEFAULT: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
  '2xl': '40px',
  '3xl': '64px',
};

export const backdropBlur = {
  none: '0',
  sm: '4px',
  DEFAULT: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
};

export const breakpoints = {
  xs: '320px',
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
};

export const containers = {
  xs: '320px',
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  full: '100%',
};

export const iconSizes = {
  xs: '12px',
  sm: '16px',
  md: '20px',
  lg: '24px',
  xl: '32px',
  '2xl': '40px',
};

export const icons = {
  navigation: [
    'Home', 'Menu', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
    'ChevronLeft', 'ChevronRight', 'ChevronUp', 'ChevronDown',
    'ChevronsLeft', 'ChevronsRight', 'ExternalLink', 'MoreHorizontal', 'MoreVertical',
  ],
  actions: [
    'Plus', 'Minus', 'X', 'Check', 'Edit', 'Trash2', 'Copy', 'Download',
    'Upload', 'Share', 'RefreshCw', 'RotateCcw', 'Save', 'Send', 'Play', 'Pause',
  ],
  status: [
    'AlertCircle', 'AlertTriangle', 'CheckCircle', 'XCircle', 'Info',
    'HelpCircle', 'Clock', 'Loader', 'Zap', 'Shield', 'ShieldCheck',
  ],
  data: [
    'BarChart2', 'PieChart', 'TrendingUp', 'TrendingDown', 'Activity',
    'Database', 'FileText', 'File', 'Folder', 'FolderOpen', 'Archive',
  ],
  communication: [
    'Mail', 'MessageSquare', 'MessageCircle', 'Bell', 'BellOff', 'Phone', 'Video',
  ],
  user: [
    'User', 'Users', 'UserPlus', 'UserMinus', 'UserCheck', 'UserX', 'Settings', 'LogOut', 'LogIn',
  ],
  misc: [
    'Search', 'Filter', 'Eye', 'EyeOff', 'Lock', 'Unlock', 'Key', 'Calendar',
    'Star', 'Heart', 'Bookmark', 'Flag', 'Tag', 'Hash', 'Link', 'Globe',
  ],
};

export const zIndex = {
  hide: -1,
  auto: 'auto',
  base: 0,
  docked: 10,
  dropdown: 1000,
  sticky: 1100,
  banner: 1200,
  overlay: 1300,
  modal: 1400,
  popover: 1500,
  skipLink: 1600,
  toast: 1700,
  tooltip: 1800,
};

// Focus ring shadows — brand color at standard opacities
export const focusRings = {
  brand: '0 0 0 3px rgba(185,29,143,0.12)',        // inputs, dropdowns, selects
  brandMedium: '0 0 0 3px rgba(185,29,143,0.18)',  // toggles
  brandStrong: '0 0 0 3px rgba(185,29,143,0.20)',  // primary buttons
};

export const transitions = {
  duration: {
    fastest: '50ms',
    faster: '100ms',
    fast: '150ms',
    normal180: '180ms',  // micro-interactions: toggles, draft messages, toast fade
    normal: '200ms',
    slow: '300ms',
    slower: '400ms',
    slowest: '500ms',
  },
  timing: {
    linear: 'linear',
    ease: 'ease',
    easeIn: 'ease-in',
    easeOut: 'ease-out',
    easeInOut: 'ease-in-out',
  },
};

// ── Logo ─────────────────────────────────────────────────────────────────────
// Source: eGain Brand Identity Manual 2026
export const logo = {
  // Asset paths (relative to /frontend/)
  src: {
    // Full-colour logo — use on white or light backgrounds
    default: 'product/eGain-logo.webp',
    // White-on-black variant (white letterforms, magenta dot on 'i') — use on dark/black backgrounds
    // File not yet available; request from design@egain.com
    white: null as string | null,
  },

  alt: 'eGain',

  // Approved logo variants per brand guide 2026
  variants: {
    // "eG" and "n" in #000000, "ai" in eGain Magenta (#B91D8F)
    fullColor: 'Full-colour (default): black wordmark with magenta "ai" — use on white/light backgrounds only',
    // All letterforms white, magenta dot on "i" retained
    white:     'White: use on black (#000000) backgrounds only',
    // All letterforms in black — for B&W collateral
    black:     'Black: use on white (#FFFFFF) backgrounds only; monochrome collateral',
  },

  // Clearspace rules (unit = cap-height of the logo, denoted "x" in brand guide)
  clearspace: {
    minimum:     '1x on all sides (cap-height of the logo)',
    recommended: '2x below the logo baseline (as shown in brand guide diagram)',
  },

  // DO rules
  do: [
    'Use only on white, black, or sufficiently contrasting solid backgrounds',
    'Maintain minimum clearspace of 1x (cap-height) on all sides',
    'Use the provided .webp file at its intended proportions — do not crop or resize disproportionately',
    'Use full-colour variant on light backgrounds; white variant on dark/black backgrounds',
  ],

  // DO NOT rules (from "Unacceptable Uses" page)
  doNot: [
    'DO NOT reproduce in any colour other than black or white (full-colour variant uses approved assets only)',
    'DO NOT use transparency — logo must appear at 100% opacity',
    'DO NOT add drop shadows or other visual effects',
    'DO NOT rotate, skew, or reflect',
    'DO NOT use the logo in outline form',
    'DO NOT alter the position or alignment of the approved lock-up',
    'DO NOT stretch, condense, or distort',
    'DO NOT add descriptors or additional elements to the wordmark',
    'DO NOT use gradient fills',
    'DO NOT place on backgrounds that do not provide sufficient contrast',
    'DO NOT place over photography or illustration that impairs legibility',
  ],
};
