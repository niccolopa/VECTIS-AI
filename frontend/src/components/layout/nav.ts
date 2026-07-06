import type { ComponentType, SVGProps } from "react";
import {
  IconDataset,
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
  // Marks the start of the secondary "Origin Demo" archive group: this item and
  // everything after it render in a collapsed-by-default section below a divider,
  // so a new user can never mistake the V1 California Case Study for the
  // planet-scale system. The value is the group's heading.
  section?: string;
}

// Sidebar navigation — the operational sections of the VECTIS console.
// Ordered global-platform first, then the collapsed V1 origin-demo archive.
export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: IconOverview },
  { to: "/terminal", label: "Global Terminal", icon: IconTerminal },
  { to: "/simulations", label: "Simulations", icon: IconSimulation },
  { to: "/datasets", label: "Datasets", icon: IconDataset },
  {
    to: "/risk",
    label: "California Case Study",
    icon: IconRisk,
    section: "Origin Demo · V1 Archive",
  },
  { to: "/reports", label: "Case Study Reports", icon: IconReport },
];
