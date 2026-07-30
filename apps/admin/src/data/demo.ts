import type { AnalysisJob } from '../types';
export const demoJobs:AnalysisJob[]=[
 {id:'job-1048',subject:'Person 017',assetName:'interview_0831.mp4',status:'SUCCEEDED',createdAt:'Сегодня, 08:02',decision:{label:'SUSPICIOUS',riskScore:.82,qualityScore:.71,modelVersion:'motion-0.9.4',evidence:[{code:'MOUTH_CHEEK_LAG',contribution:.31,message:'Нетипичная задержка движения щёк',startMs:74230,endMs:75020},{code:'JAW_RANGE_LOW',contribution:.22,message:'Амплитуда челюсти ниже персональной нормы',startMs:151440,endMs:152110}]}},
 {id:'job-1047',subject:'Person 042',assetName:'clip_229.mov',status:'INSUFFICIENT_DATA',createdAt:'Сегодня, 07:51',decision:{label:'INSUFFICIENT_DATA',riskScore:0,qualityScore:.29,modelVersion:'quality-v1',evidence:[{code:'EXCESSIVE_GAPS',contribution:0,message:'Трек лица содержит длинные разрывы'}]}},
 {id:'job-1046',subject:'Person 009',assetName:'recording_14.mp4',status:'SUCCEEDED',createdAt:'Вчера, 22:19',decision:{label:'CONSISTENT',riskScore:.13,qualityScore:.88,modelVersion:'motion-0.9.4',evidence:[]}},
 {id:'job-1045',subject:'Person 031',assetName:'cam2_take7.mp4',status:'RUNNING',createdAt:'Вчера, 21:43'}
];
