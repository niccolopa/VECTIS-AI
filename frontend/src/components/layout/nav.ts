import type { ComponentType, SVGProps } from "react";
import {
  IconActivity,
  IconDataset,
  IconLive,
  IconMap,
  IconOverview,
  IconReport,
  IconRisk,
  IconSimulation,
  IconTerminal,
} from "@/components/layout/icons";

export interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  // Optional group heading rendered above this item in the sidebar. Used to
  // separate the global V4 platform from the fixed V1 California demo so a new
  // user can never mistake the legacy Case Study for the planet-scale system.
  section?: string;
}

// Sidebar navigation — the operational sections of the VECTIS console.
// Ordered global-platform first, then the clearly-fenced V1 legacy demo.
export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: IconOverview },
  { to: "/terminal", label: "Global Terminal", icon: IconTerminal },
  { to: "/live", label: "Live Intelligence", icon: IconLive },
  { to: "/dashboard", label: "Decision Intelligence", icon: IconActivity },
  { to: "/maps", label: "Maps", icon: IconMap },
  { to: "/simulations", label: "Simulations", icon: IconSimulation },
  { to: "/datasets", label: "Datasets", icon: IconDataset },
  {
    to: "/risk",
    label: "California Case Study",
    icon: IconRisk,
    section: "V1 Legacy Demo",
  },
  { to: "/reports", label: "Case Study Reports", icon: IconReport },
];
