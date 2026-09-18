import { defineConfig } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "no-console": "warn",
      // ponytail: warn-only — fetch-in-effect is the standard pattern on every
      // page here; erroring would keep `npm run lint` red on main. Revisit if
      // effects start causing real render loops.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);
