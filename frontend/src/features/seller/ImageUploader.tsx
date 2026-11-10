import { useRef, useState } from "react";
import { ImagePlus, Star, X } from "lucide-react";
import { uploadApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

const MAX_IMAGES = 10;
const MAX_MB = 5;
const ACCEPT = "image/jpeg,image/png,image/webp,image/gif";

interface Props {
  urls: string[];
  onChange: (urls: string[]) => void;
  onBusyChange?: (busy: boolean) => void;
}

/** Pick files from disk; each is uploaded immediately and shown as a thumbnail. First image is the primary one. */
export function ImageUploader({ urls, onChange, onBusyChange }: Props) {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(0);

  const busy = (n: number) => {
    setUploading(n);
    onBusyChange?.(n > 0);
  };

  const pick = async (files: FileList | null) => {
    if (!files?.length) return;
    const room = MAX_IMAGES - urls.length;
    const chosen = Array.from(files).slice(0, Math.max(room, 0));
    if (files.length > room) toast.error(`You can add at most ${MAX_IMAGES} images.`);

    const valid = chosen.filter((f) => {
      if (f.size > MAX_MB * 1024 * 1024) {
        toast.error(`${f.name} is larger than ${MAX_MB} MB.`);
        return false;
      }
      return true;
    });
    if (!valid.length) return;

    busy(valid.length);
    const uploaded: string[] = [];
    await Promise.all(
      valid.map(async (f) => {
        try {
          uploaded.push((await uploadApi.image(f)).url);
        } catch (e) {
          toast.error(`${f.name}: ${(e as Error).message}`);
        }
      }),
    );
    busy(0);
    if (uploaded.length) onChange([...urls, ...uploaded]);
    if (input.current) input.current.value = "";
  };

  const makePrimary = (i: number) => onChange([urls[i], ...urls.filter((_, idx) => idx !== i)]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        {urls.map((url, i) => (
          <div key={url} className="group relative h-24 w-24 overflow-hidden rounded-md border bg-muted">
            <img src={url} alt={`Product image ${i + 1}`} className="h-full w-full object-cover" />
            {i === 0 && (
              <span className="absolute left-1 top-1 rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground">
                Primary
              </span>
            )}
            <div className="absolute inset-x-0 bottom-0 flex justify-between bg-black/50 p-1 opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100">
              {i !== 0 ? (
                <button type="button" aria-label="Make primary image" onClick={() => makePrimary(i)} className="text-white">
                  <Star className="h-4 w-4" />
                </button>
              ) : (
                <span />
              )}
              <button
                type="button"
                aria-label={`Remove image ${i + 1}`}
                onClick={() => onChange(urls.filter((_, idx) => idx !== i))}
                className="text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
        {Array.from({ length: uploading }).map((_, i) => (
          <div key={`u${i}`} className="flex h-24 w-24 animate-pulse items-center justify-center rounded-md border bg-muted text-xs text-muted-foreground">
            Uploading…
          </div>
        ))}
      </div>

      <input
        ref={input}
        id="pimg"
        type="file"
        accept={ACCEPT}
        multiple
        className="sr-only"
        onChange={(e) => void pick(e.target.files)}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={urls.length >= MAX_IMAGES || uploading > 0}
        onClick={() => input.current?.click()}
      >
        <ImagePlus className="h-4 w-4" /> {urls.length ? "Add more images" : "Upload images"}
      </Button>
      <p className="text-xs text-muted-foreground">
        JPEG, PNG, WebP or GIF, up to {MAX_MB} MB each. The first image is the primary one; hover a thumbnail to change it.
      </p>
    </div>
  );
}
