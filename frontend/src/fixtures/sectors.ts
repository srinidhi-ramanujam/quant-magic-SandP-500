export type Sector = {
  id: string;
  label: string;
};

export const TOP_SECTORS: Sector[] = [
  { id: "technology", label: "Technology" },
  { id: "information_technology", label: "Information Technology" },
  { id: "financials", label: "Banking / Financials" },
  { id: "healthcare", label: "Healthcare" },
  { id: "consumer_discretionary", label: "E-commerce / Consumer Discretionary" },
  { id: "industrials", label: "Industrials / Manufacturing" },
  { id: "energy", label: "Energy" },
  { id: "utilities", label: "Utilities" },
  { id: "communications", label: "Communications" },
  { id: "materials", label: "Materials" },
];
