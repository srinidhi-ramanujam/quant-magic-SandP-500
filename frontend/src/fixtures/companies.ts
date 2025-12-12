export type FeaturedCompany = {
  name: string;
  ticker?: string;
};

export const FEATURED_COMPANIES: FeaturedCompany[] = [
  { name: "Apple", ticker: "AAPL" },
  { name: "Microsoft", ticker: "MSFT" },
  { name: "Nvidia", ticker: "NVDA" },
  { name: "Amazon", ticker: "AMZN" },
  { name: "Alphabet", ticker: "GOOGL" },
  { name: "Tesla", ticker: "TSLA" },
  { name: "Meta Platforms", ticker: "META" },
  { name: "JPMorgan Chase", ticker: "JPM" },
  { name: "UnitedHealth", ticker: "UNH" },
  { name: "Exxon Mobil", ticker: "XOM" },
];
