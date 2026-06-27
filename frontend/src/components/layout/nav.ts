import type { ComponentType, SVGProps } from "react";
import {
  IconDataset,
  IconMap,
  IconOverview,
  IconReport,
  IconRisk,
  IconSimulation,
} from "@/components/layout/icons";

export interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

// Sidebar navigation — the operational sections of the VECTIS console.
export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: IconOverview },
  { to: "/risk", label: "Risk Intelligence", icon: IconRisk },
  { to: "/maps", label: "Maps", icon: IconMap },
  { to: "/reports", label: "Reports", icon: IconReport },
  { to: "/simulations", label: "Simulations", icon: IconSimulation },
  { to: "/datasets", label: "Datasets", icon: IconDataset },
];
