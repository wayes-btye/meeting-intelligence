"use client";

interface Props {
  chunking: string;
  retrieval: string;
  onChunkingChange: (v: string) => void;
  onRetrievalChange: (v: string) => void;
}

// Radio-button strategy selectors for chunking and retrieval
export function StrategySelector({
  chunking,
  retrieval,
  onChunkingChange,
  onRetrievalChange,
}: Props) {
  return (
    <div className="flex flex-wrap gap-6">
      <fieldset>
        <legend className="text-sm font-medium mb-2">Chunking Strategy</legend>
        <div className="flex gap-4">
          {["naive", "speaker_turn"].map((val) => (
            <label
              key={val}
              className="flex items-center gap-2 cursor-pointer text-sm"
            >
              <input
                type="radio"
                name="chunking"
                value={val}
                checked={chunking === val}
                onChange={() => onChunkingChange(val)}
                className="accent-primary"
              />
              {val === "naive" ? "Naive" : "Speaker Turn"}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="text-sm font-medium mb-2">Retrieval Strategy</legend>
        <div className="flex gap-4">
          {["semantic", "hybrid"].map((val) => (
            <label
              key={val}
              className="flex items-center gap-2 cursor-pointer text-sm"
            >
              <input
                type="radio"
                name="retrieval"
                value={val}
                checked={retrieval === val}
                onChange={() => onRetrievalChange(val)}
                className="accent-primary"
              />
              {val === "semantic" ? "Semantic" : "Hybrid"}
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  );
}
