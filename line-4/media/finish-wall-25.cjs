// Consume the image tool's edit, keeping its pigment only on previously bare rock.
// Requires the existing local PNG/JPEG codec; no dependency is installed.
const fs = require('node:fs');
const crypto = require('node:crypto');
const {decode, encode, thumbnail} = require('../../line-1/media/finish-wall.cjs');
const sha = raw => crypto.createHash('sha256').update(raw).digest('hex');
const beforeBytes = fs.readFileSync('artifacts/line-4/wall-v5.png');
const before = decode(beforeBytes);
const generatedBytes = fs.readFileSync('artifacts/line-4/wall-v6.png');
const generated = decode(generatedBytes);
const out = {...before, pixels: Buffer.from(before.pixels)};
const bounds = [895, 630, 1030, 755];
let changed=0, outside=0;
for(let y=0;y<before.height;y++) for(let x=0;x<before.width;x++) {
  const i=(y*before.width+x)*3;
  const clamp = value => Math.max(0,Math.min(1,value));
  // Trace only the generated silhouette, with a narrow soft edge. The sieve's
  // upper lip slopes upward to the right; its underside is a shallow ellipse.
  const top = 705 - (x-903)*.15;
  const radial = Math.hypot((x-963)/63,(y-691)/59);
  const bowl = clamp((y-top)/2)*clamp((1-radial)*25);
  const stones = Math.max(clamp((15-Math.hypot(x-945,y-679))/2),
                          clamp((15-Math.hypot(x-975,y-652))/2));
  const alpha = Math.max(bowl,stones);
  if(alpha) for(let c=0;c<3;c++)
    out.pixels[i+c]=Math.round(before.pixels[i+c]*(1-alpha)+generated.pixels[i+c]*alpha);
  if(!out.pixels.subarray(i,i+3).equals(before.pixels.subarray(i,i+3))) {
    changed++;
    if(x<bounds[0] || y<bounds[1] || x>bounds[2] || y>bounds[3]) outside++;
  }
}
if(outside || changed<500) throw Error('preservation or empty-mark check failed');
const png=encode(out), jpg=thumbnail(out);
if(!decode(png).pixels.equals(out.pixels)) throw Error('PNG roundtrip failed');
if(jpg.length>100000) throw Error('JPEG exceeds 100 KB');
fs.writeFileSync('artifacts/line-4/wall-v6.png',png);
if(fs.existsSync('artifacts/line-4/wall.png')) fs.unlinkSync('artifacts/line-4/wall.png');
fs.symlinkSync('wall-v6.png','artifacts/line-4/wall.png');
// Save the preview bytes under artifacts; the beside-record hard link is the
// same image, not an extra draft, and survives source/output split delivery.
fs.writeFileSync('artifacts/line-4/25.jpg',jpg);
if(!fs.existsSync('dist/line-4/25.jpg')) fs.linkSync('artifacts/line-4/25.jpg','dist/line-4/25.jpg');
const review={source:'artifacts/line-4/wall-v5.png',source_sha256:sha(beforeBytes),
  generated_sha256:sha(generatedBytes),wall:'artifacts/line-4/wall-v6.png',sha256:sha(png),
  width:before.width,height:before.height,format:'PNG',bytes:png.length,
  preview:'dist/line-4/25.jpg',preview_width:512,preview_height:512,preview_format:'JPEG',preview_bytes:jpg.length,
  changed_pixels:changed,changed_pixels_outside_addition:outside,addition_bounds_inclusive:bounds,
  png_roundtrip_passed:true};
fs.writeFileSync('line-4/media-check-25.json',JSON.stringify(review,null,2)+'\n');
console.log(JSON.stringify(review,null,2));
