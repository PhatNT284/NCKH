import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import os from 'node:os';
import {constants as fsConstants} from 'node:fs';
const modules = process.env.D6_ARTIFACT_NODE_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const require = createRequire(path.join(modules, '..', 'd6-export.cjs'));
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);

// Called by src.d6_export; does not evaluate models or modify source records.
const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) throw new Error('Usage: node src/d6_excel.mjs <JSON file or records directory> <output.xlsx>');
const source = path.resolve(inputPath);
const out = path.dirname(path.resolve(outputPath));
const files = (await fs.stat(source)).isDirectory()
  ? (await fs.readdir(source)).filter(x=>x.endsWith('.json')).sort().map(x=>path.join(source,x))
  : [source];
if (!files.length) throw new Error('No mission records found');
const records = await Promise.all(files.map(async file=>({file:path.basename(file),...JSON.parse(await fs.readFile(file,'utf8'))})));
for (const file of [outputPath]) {
  try { await fs.access(file); throw new Error('Output already exists: '+file); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
}
await fs.mkdir(out,{recursive:true});
const wb = Workbook.create();
const missing = x=>x===null || x===undefined ? 'Không có dữ liệu' : x;
const text = x=>Array.isArray(x) ? (x.length ? x.map(y=>typeof y==='object'?JSON.stringify(y):String(y)).join('\n') : 'Không có') : missing(x);
const descriptions = {cmu_diagnostic:'Cấu hình CMU chẩn đoán',conditional:'Phán quyết có điều kiện',expired_weather:'Thời tiết hết hạn',fly:'Đánh giá FLY ban đầu',invalid_soc:'SoC không hợp lệ',missing_soc:'Thiếu SoC',nan_wind:'Gió NaN',no_fly:'Không đủ biên dự trữ',preflight_reassessment:'Đánh giá lại trước bay',reserve_boundary:'Cận biên dự trữ',tb48d:'Pin TB48D',wind_veto:'Gió vi phạm luật cứng'};
const summary=[], inputs=[], rules=[], workflow=[];
for(const {record:r,file} of records){
 const a=r.snapshot.assessment, d=a.result.decision??{}, i=a.inputs, w=r.workflow;
 const id=a.assessment_id;
 summary.push([id,descriptions[id]??id,a.result.verdict,missing(d.e_required_Wh),missing(d.e_available_Wh),missing(d.margin_Wh),missing(d.margin_ratio),missing(d.r_min),w.assessment_status,w.mission_status,text(a.result.reasons)]);
 inputs.push([id,i.profile,i.battery_type,missing(i.distance_2d_m),missing(i.payload_g),missing(i.speed_commanded_ms),missing(i.altitude_m),missing(i.soc),missing(i.soh),missing(i.ambient_temp_c),missing(i.wind_forecast_ms),new Date(a.assessed_at),a.weather.source,new Date(a.weather.observed_at),new Date(a.weather.valid_until),text(a.normalization_nonfinite_to_null),file]);
 for(const c of d.hard_rule_report?.checks??[]){rules.push([id,c.rule_id,c.severity,c.status,c.detail,c.source]);}
 workflow.push([id,w.assessment_status,w.mission_status,text(w.stale_reason),missing(w.approval_action),missing(w.approval_actor_role),w.approval_timestamp ? new Date(w.approval_timestamp) : 'Không có',missing(w.preflight_reassessment_id),w.observed_outcome.outcome,text(a.result.missing_inputs),text(a.result.invalid_inputs),text(a.result.weather_issues),JSON.stringify(w.events)]);
}
const defs=[
 ['Tong hop',`D6 — Tổng hợp ${records.length} bản ghi`, ['Mã đánh giá','Ca kiểm thử','Phán quyết khi đánh giá','Năng lượng cần (Wh)','Năng lượng có (Wh)','Biên năng lượng (Wh)','Tỷ lệ biên dự trữ','Ngưỡng dự trữ r_min','Trạng thái đánh giá','Trạng thái nhiệm vụ','Lý do phán quyết'],summary,[28,32,24,22,22,22,22,22,24,24,72], 'FLY là phán quyết lịch sử; xem trạng thái đánh giá và nhiệm vụ để biết bản ghi đã hết hiệu lực hay bị chặn.'],
 ['Dau vao','D6 — Đầu vào từng ca thử',['Mã đánh giá','Cấu hình','Loại pin','Tổng đường bay (m)','Tải trọng (g)','Tốc độ (m/s)','Độ cao (m)','SoC','SoH','Nhiệt độ (°C)','Gió (m/s)','Thời điểm đánh giá UTC','Nguồn thời tiết','Thời tiết quan sát UTC','Thời tiết hiệu lực đến UTC','Chuẩn hóa NaN/vô hạn','File nguồn'],inputs,[28,25,18,22,18,18,18,18,18,18,18,26,31,26,28,45,34], 'SoC/SoH hiển thị dạng %. Ô thiếu dữ liệu được ghi rõ; NaN/vô hạn đã được chuẩn hóa trong bản ghi gốc.'],
 ['Luat kiem tra','D6 — Chi tiết luật kiểm tra',['Mã đánh giá','Mã luật','Mức xử lý','Kết quả','Giải thích trong bản ghi','Nguồn luật'],rules,[28,16,22,20,100,60], 'VETO: luật có quyền chặn. DOWNGRADE: luật hạ mức. Nội dung giải thích giữ nguyên từ bản ghi.'],
 ['Quy trinh','D6 — Trạng thái và lịch sử',['Mã đánh giá','Trạng thái đánh giá','Trạng thái nhiệm vụ','Lý do hết hiệu lực','Thao tác duyệt','Vai trò duyệt','Thời điểm duyệt UTC','Liên kết đánh giá lại','Kết cục thực tế','Đầu vào thiếu','Đầu vào sai','Vấn đề thời tiết','Sự kiện gốc'],workflow,[28,24,24,55,24,24,26,30,22,40,45,50,100], 'UNKNOWN: chưa có bằng chứng về kết cục bay thực tế. Lịch sử và trạng thái được lấy nguyên từ bản ghi đã xuất.']
];
function col(n){let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26);}return s;}
for(const [name,,headers,rows,widths] of defs){
 const s=wb.worksheets.add(name),last=col(headers.length),end=1+rows.length;
 s.showGridLines=true;
 s.getRange(`A1:${last}${end}`).values=[headers,...rows];
 const table=s.tables.add(`A1:${last}${end}`,true,'D6_'+name.replaceAll(' ','_'));
 table.style='TableStyleMedium2';
 table.showFilterButton=true;
 s.getRange(`A1:${last}${end}`).format={fill:'#FFFFFF',font:{name:'Arial',size:11,color:'#000000'},verticalAlignment:'center',rowHeight:24};
 s.getRange(`A1:${last}1`).format={fill:'#19365B',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'left',verticalAlignment:'center',rowHeight:36};
 for(let row=2;row<=end;row++)s.getRange(`A${row}:${last}${row}`).format.fill=row%2===0?'#C0E6F5':'#FFFFFF';
 s.getRange(`A1:${last}${end}`).format.borders={preset:'all',style:'thin',color:'#B8C4CE'};
 s.getRange(`A2:${last}${end}`).format.wrapText=true;
 for(let j=0;j<headers.length;j++)s.getRange(`${col(j+1)}1:${col(j+1)}${end}`).format.columnWidth=widths[j];
 s.freezePanes.freezeRows(1);s.freezePanes.freezeColumns(1);
 if(name==='Tong hop'){
  s.getRange(`D2:F${end}`).setNumberFormat('0.0000');s.getRange(`G2:H${end}`).setNumberFormat('0.0%');
 }
 if(name==='Dau vao'){s.getRange(`H2:I${end}`).setNumberFormat('0.0%');for(const c of ['L','N','O'])s.getRange(`${c}2:${c}${end}`).setNumberFormat('yyyy-mm-dd hh:mm:ss');}
 if(name==='Quy trinh')s.getRange(`G2:G${end}`).setNumberFormat('yyyy-mm-dd hh:mm:ss');
 s.getRange(`A2:${last}${end}`).format.autofitRows();
 for(let row=0;row<rows.length;row++)for(let j=0;j<headers.length;j++){const actual=s.getCell(row+1,j).values[0][0], expected=rows[row][j];if(expected instanceof Date)assert.ok(Math.abs(new Date(actual).getTime()-expected.getTime())<=1);else assert.deepEqual(actual,expected);}
}
wb.recalculate();
// The spreadsheet library may create an inspection sidecar when saving.
// Keep that diagnostic in a disposable directory, exposing only the workbook.
const staging = await fs.mkdtemp(path.join(os.tmpdir(), 'd6-xlsx-'));
try {
 const stagedWorkbook=path.join(staging,'mission_records.xlsx');
 await (await SpreadsheetFile.exportXlsx(wb)).save(stagedWorkbook);
 await fs.copyFile(stagedWorkbook,outputPath,fsConstants.COPYFILE_EXCL);
} finally {
 assert.equal(path.dirname(staging),path.resolve(os.tmpdir()));
 await fs.rm(staging,{recursive:true,force:true});
}
console.log(JSON.stringify({records:records.length,rules:rules.length,output:outputPath}));

process.exitCode = 0;
