/**
 * Upload a local file to a temporary public host and return a direct-download
 * URL. Creatomate (and other render/publish APIs) need media at a fetchable URL
 * rather than an inline base64 blob, so this bridges our local output files to
 * something they can pull.
 *
 * Uses tmpfiles.org (no account needed; files live ~1 hour — long enough for a
 * render). This is a pragmatic stopgap; swap in S3/GCS/Cloudinary for a durable
 * production host by replacing uploadToTempHost().
 */
import fs from "node:fs";
import axios from "axios";
import FormData from "form-data";

export async function uploadToTempHost(filePath) {
  const form = new FormData();
  form.append("file", fs.createReadStream(filePath));
  const res = await axios.post("https://tmpfiles.org/api/v1/upload", form, {
    headers: form.getHeaders(),
    maxBodyLength: Infinity,
    timeout: 120000
  });
  const url = res?.data?.data?.url;
  if (!url) throw new Error("tmpfiles upload returned no url");
  // Convert the viewer URL into a direct-download URL.
  return url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/");
}
