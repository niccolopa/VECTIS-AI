// Minimal inline SVG icon set (no icon-library dependency). 1.5px stroke, currentColor.
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const base = (props: IconProps) => ({
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...props,
});

export const IconOverview = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3" y="3" width="7" height="9" rx="1" />
    <rect x="14" y="3" width="7" height="5" rx="1" />
    <rect x="14" y="12" width="7" height="9" rx="1" />
    <rect x="3" y="16" width="7" height="5" rx="1" />
  </svg>
);

export const IconRisk = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3c2 3 5 5 5 9a5 5 0 01-10 0c0-2 1-3 2-4 .5 2 1.5 2.5 1.5 2.5C11 9 11 6 12 3z" />
  </svg>
);

export const IconMap = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" />
    <path d="M9 4v14M15 6v14" />
  </svg>
);

export const IconReport = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6 3h8l4 4v14H6z" />
    <path d="M14 3v4h4M9 13h6M9 17h6" />
  </svg>
);

export const IconSimulation = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3" />
    <path d="M7.5 15h9" />
  </svg>
);

export const IconDataset = (p: IconProps) => (
  <svg {...base(p)}>
    <ellipse cx="12" cy="5" rx="8" ry="3" />
    <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
  </svg>
);

export const IconMenu = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </svg>
);

export const IconActivity = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M3 12h4l3 8 4-16 3 8h4" />
  </svg>
);

export const IconTerminal = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3" y="4" width="18" height="16" rx="1.5" />
    <path d="M7 9l3 3-3 3M12 15h5" />
  </svg>
);

export const IconLive = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="2.5" />
    <path d="M7.8 7.8a6 6 0 000 8.5M16.2 16.3a6 6 0 000-8.5M4.9 4.9a10 10 0 000 14.2M19.1 19.1a10 10 0 000-14.2" />
  </svg>
);
