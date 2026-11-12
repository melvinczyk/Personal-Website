// Echo Scout device emulator: the canvas demo on its project card. Loaded on
// demand by portfolio.js the first time that card opens.
let _esDemoRAF = null;

function startEchoScoutDemo(canvasId) { // eslint-disable-line no-unused-vars
  if (_esDemoRAF) { cancelAnimationFrame(_esDemoRAF); _esDemoRAF = null; }

  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let screen    = 'loading';
  let subTab    = 0;
  let t         = 0;
  let loadPct   = 0;
  let lastScreen = '';
  let lastSubTab = -1;
  let anglState = 0;
  const SCOPE_SAMPLES = 240;
  const _scopeBuf = [new Float32Array(SCOPE_SAMPLES), new Float32Array(SCOPE_SAMPLES), new Float32Array(SCOPE_SAMPLES)];
  let _scopeHead = 0;

  const resetBtn = document.getElementById(`${canvasId}-reset`);
  if (resetBtn) resetBtn.addEventListener('click', () => {
    screen='loading'; subTab=0; t=0; loadPct=0; lastScreen=''; lastSubTab=-1; anglState=0; _scopeHead=0;
  });

  const K = { BG:'#000000', G:'#00FC00', DIM:'#006000', FAINT:'#003000',
              SEP:'#005800', RED:'#FF0000', AMB:'#F85C00', WHT:'#FFFFFF' };

  function fr(x,y,w,h,c)        { ctx.fillStyle=c; ctx.fillRect(x,y,w,h); }
  function dr(x,y,w,h,c)        { ctx.strokeStyle=c; ctx.lineWidth=1; ctx.strokeRect(x+.5,y+.5,w-1,h-1); }
  function hl(x,y,l,c)          { ctx.fillStyle=c; ctx.fillRect(x,y,l,1); }
  function vl(x,y,l,c)          { ctx.fillStyle=c; ctx.fillRect(x,y,1,l); }
  function fc(cx,cy,r,c)        { ctx.fillStyle=c; ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.fill(); }
  function lnC(x1,y1,x2,y2,c)  { ctx.strokeStyle=c; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke(); }
  function txt(s,x,y,sz,c,al='left') {
    ctx.save(); ctx.fillStyle=c;
    ctx.font=`${sz===1?8:sz===2?13:sz===4?24:8}px "Courier New",monospace`;
    ctx.textBaseline='top'; ctx.textAlign=al; ctx.fillText(s,x,y); ctx.restore();
  }
  function ctxt(s,cx,y,sz,c) { txt(s,cx,y,sz,c,'center'); }

  function drawArt(lines, sx, sy, cw, lh, col) {
    ctx.save(); ctx.fillStyle=col;
    ctx.font=`${lh}px "Courier New",monospace`;
    ctx.textBaseline='top';
    for (let row=0; row<lines.length; row++) {
      const line=lines[row];
      for (let c=0; c<line.length; c++) {
        if (line[c]===' ') continue;
        ctx.fillText(line[c], sx+c*cw, sy+row*lh);
      }
    }
    ctx.restore();
  }

  const ECHO_ART = [
    '___________      .__          ',
    '\\_   _____/ ____ |  |__   ____',
    ' |    __)__/ ___\\|  |  \\ /  _ \\',
    ' |        \\  \\___|   Y  (  <_> )',
    '/_______  /\\___  >___|  /\\____/',
    '        \\/     \\/     \\/       ',
  ];
  const SCOUT_ART = [
    '  _________                    __  ',
    ' /   _____/ ____  ____  __ ___/  |_',
    ' \\_____  \\_/ ___\\/  _ \\|  |  \\   __\\',
    ' /        \\  \\__(  <_> )  |  /|  | ',
    '/_______  /\\___  >____/|____/ |__| ',
    '        \\/     \\/                  ',
  ];

  function drawHeader(title, showCal=false) {
    fr(0,0,240,28,K.BG); hl(0,27,240,K.SEP);
    ctx.save(); ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    ctx.beginPath(); ctx.roundRect(3,3,64,22,[3]); ctx.stroke();
    if (showCal) { ctx.beginPath(); ctx.roundRect(173,3,64,22,[3]); ctx.stroke(); }
    ctx.restore();
    ctxt('< MENU',35,7,2,K.DIM); ctxt(title,120,9,2,K.G);
    if (showCal) ctxt('CAL',205,7,2,K.DIM);
  }

  function drawTabBar(labels, active) {
    const tw=Math.floor(240/labels.length);
    fr(0,280,240,40,K.BG); hl(0,280,240,K.SEP);
    labels.forEach((lbl,i) => {
      const x=i*tw;
      if(i===active) { fr(x,281,tw-1,39,K.FAINT); hl(x,280,tw,K.G); ctxt(lbl,x+tw/2,293,1,K.G); }
      else ctxt(lbl,x+tw/2,293,1,K.DIM);
    });
  }

  function drawLoading() {
    fr(0,0,240,320,K.BG);
    dr(2,2,236,316,K.FAINT);
    drawArt(ECHO_ART,  42, 16, 5, 9, K.G);
    drawArt(SCOUT_ART, 30, 80, 5, 9, K.G);
    ctxt('FLASHING SENSOR FIRMWARE',120,162,1,K.DIM);
    const BX=20,BY=185,BW=200,BH=14;
    dr(BX-1,BY-1,BW+2,BH+2,K.DIM);
    const fill=Math.round((BW-4)*loadPct/100);
    if(fill>0) fr(BX+2,BY+2,fill,BH-4,K.G);
    ctxt(`${Math.round(loadPct)}%`,120,BY+BH+6,1,K.DIM);
  }

  function drawMenu() {
    fr(0,0,240,320,K.BG);
    dr(2,2,236,316,K.FAINT);
    dr(8,8,224,138,K.DIM); dr(12,12,216,130,K.G);
    hl(16,16,16,K.G); vl(16,16,16,K.G);
    hl(207,16,16,K.G); vl(223,16,16,K.G);
    hl(16,138,16,K.G); vl(16,123,16,K.G);
    hl(207,138,16,K.G); vl(223,123,16,K.G);
    fr(70,137,100,6,K.BG);
    ctxt('VERSION: 1.0',120,137,1,K.DIM);
    drawArt(ECHO_ART,  42, 16, 5, 9, K.G);
    drawArt(SCOUT_ART, 30, 80, 5, 9, K.G);
    const sy=147, sh=13;
    fr(0,sy,240,sh,K.BG);
    hl(8,sy,224,K.SEP); hl(8,sy+sh-1,224,K.SEP);
    vl(88,sy+2,sh-4,K.SEP); vl(160,sy+2,sh-4,K.SEP);
    function sUnit(cx,label) {
      const w=label.length*6+13, sx2=cx-w/2;
      fc(sx2+3,sy+sh/2,3,K.G);
      ctx.save(); ctx.fillStyle=K.G; ctx.font='8px "Courier New",monospace';
      ctx.textBaseline='middle'; ctx.textAlign='left';
      ctx.fillText(label,sx2+10,sy+sh/2); ctx.restore();
    }
    sUnit(44,'RADAR'); sUnit(124,'IMU'); sUnit(200,'TOF');
    hl(8,158,224,K.SEP);
    const bx=12,by=160,bw=216,bh=44, arm=10;
    dr(bx,by,bw,bh,K.DIM); dr(bx+2,by+2,bw-4,bh-4,K.G);
    hl(bx+6,by+6,arm,K.G); vl(bx+6,by+6,arm,K.G);
    hl(bx+bw-arm-6,by+6,arm,K.G); vl(bx+bw-7,by+6,arm,K.G);
    hl(bx+6,by+bh-7,arm,K.G); vl(bx+6,by+bh-arm-6,arm,K.G);
    hl(bx+bw-arm-6,by+bh-7,arm,K.G); vl(bx+bw-7,by+bh-arm-6,arm,K.G);
    const ix=bx+22, iy=by+bh/2;
    vl(ix,iy-7,14,K.G);
    lnC(ix,iy,ix-5,iy-6,K.G); lnC(ix,iy,ix+5,iy-6,K.G);
    hl(ix-6,iy,13,K.G);
    for(let a=-50;a<=50;a+=10){
      const r=a*Math.PI/180;
      ctx.fillStyle=K.G;
      ctx.fillRect(ix+Math.round(8*Math.sin(r))-0.5, iy-Math.round(8*Math.cos(r))-0.5,1,1);
      ctx.fillRect(ix+Math.round(12*Math.sin(r))-0.5,iy-Math.round(12*Math.cos(r))-0.5,1,1);
    }
    ctxt('[ RADAR ]',128,by+13,4,K.G);
    hl(8,204,224,K.SEP);
    function mBtn(bx2,by2,bw2,bh2,label) {
      dr(bx2,by2,bw2,bh2,K.DIM); dr(bx2+2,by2+2,bw2-4,bh2-4,K.G);
      ctxt(label,bx2+bw2/2,by2+bh2/2-4,1,K.G);
    }
    mBtn(8,206,108,30,'3D MAP'); mBtn(120,206,108,30,'SURVEYOR');
    hl(8,236,224,K.SEP);
    mBtn(8,238,108,26,'SCANNER'); mBtn(120,238,108,26,'ATTITUDE');
    hl(8,264,224,K.SEP);
    mBtn(8,266,108,24,'SETTINGS'); mBtn(120,266,108,24,'BATTERY');
    hl(8,290,224,K.SEP);
    dr(40,294,160,16,K.RED); ctxt('[ POWER OFF ]',120,297,1,K.RED);
  }

  const _coneCanvas=document.createElement('canvas');
  _coneCanvas.width=240; _coneCanvas.height=320;
  (function buildCone(){
    const gc=_coneCanvas.getContext('2d');
    gc.fillStyle=K.BG; gc.fillRect(0,0,240,320);
    const AX=120,AY=316,CLEN=227,HD=55,AR=4000;
    const sd=d=>Math.pow(Math.min(d/AR,1),0.75)*0.88;
    [-55,-27.5,0,27.5,55].forEach((a,i)=>{
      const r=a*Math.PI/180;
      gc.strokeStyle=(i===0||i===4)?K.DIM:K.FAINT; gc.lineWidth=1;
      gc.beginPath(); gc.moveTo(AX,AY); gc.lineTo(AX+CLEN*Math.sin(r),AY-CLEN*Math.cos(r)); gc.stroke();
    });
    [1000,2000,3000,4000].forEach((rMM,ri)=>{
      const rpx=sd(rMM)*CLEN; gc.strokeStyle=ri===3?K.DIM:K.FAINT; gc.lineWidth=1;
      gc.beginPath(); let first=true;
      for(let a=-HD;a<=HD;a+=1.5){
        const r=a*Math.PI/180,gx=AX+rpx*Math.sin(r),gy=AY-rpx*Math.cos(r);
        if(gy<28) continue;
        first?(gc.moveTo(gx,gy),first=false):gc.lineTo(gx,gy);
      }
      gc.stroke();
      const ly=Math.max(32,AY-rpx);
      gc.fillStyle=K.DIM; gc.font='8px "Courier New",monospace';
      gc.textBaseline='top'; gc.textAlign='left';
      gc.fillText(rMM>=1000?`${rMM/1000}m`:`${rMM}mm`,AX+2,ly-8);
    });
    [-55,-27.5,0,27.5,55].forEach(a=>{
      const r=a*Math.PI/180;
      const lx=Math.max(8,Math.min(232,AX+CLEN*Math.sin(r)));
      const ly=Math.max(32,Math.min(AY-10,AY-CLEN*Math.cos(r)));
      gc.fillStyle=K.DIM; gc.font='8px "Courier New",monospace';
      gc.textBaseline='top'; gc.textAlign='center';
      gc.fillText(`${a>0?'+':''}${a}`,lx,ly);
    });
    gc.fillStyle=K.G; gc.beginPath(); gc.arc(AX,AY,4,0,Math.PI*2); gc.fill();
  })();

  const _tgts=[
    {ph:0,   ps:0.009,db:1400,da:500,ab:12, aa:28},
    {ph:2.1, ps:0.015,db:850, da:320,ab:-20,aa:18},
  ];

  function drawRadar(t) {
    const AX=120,AY=316,CLEN=227,AR=4000,CTOP=28;
    const sd=d=>Math.pow(Math.min(d/AR,1),0.75)*0.88;
    const DY=30,DH=54,CW=76,DP=4;
    fr(0,0,240,320,K.BG);
    drawHeader('ECHO SCOUT');
    hl(0,DY+DH,240,K.SEP);
    for(let i=0;i<3;i++) dr(DP+i*(CW+DP),DY+2,CW,DH-4,K.DIM);
    ctxt('DIST', DP+CW/2,           DY+5,1,K.DIM);
    ctxt('ANGLE',DP+(CW+DP)+CW/2,   DY+5,1,K.DIM);
    ctxt('SPEED',DP+2*(CW+DP)+CW/2, DY+5,1,K.DIM);
    ctx.drawImage(_coneCanvas,0,CTOP,240,320-CTOP,0,CTOP,240,320-CTOP);
    const blips=_tgts.map(tg=>{
      const phase=tg.ph+t*tg.ps, dist=tg.db+tg.da*Math.sin(phase), angle=tg.ab+tg.aa*Math.sin(phase*0.7);
      const rpx=sd(dist)*CLEN, rad=angle*Math.PI/180;
      const sx=AX+rpx*Math.sin(rad), sy=AY-rpx*Math.cos(rad);
      return {dist,angle,sx,sy,ok:sy>=CTOP&&sy<316};
    });
    blips.forEach(b=>{
      if(!b.ok) return;
      const g=ctx.createRadialGradient(b.sx,b.sy,0,b.sx,b.sy,9);
      g.addColorStop(0,'rgba(255,0,0,0.55)'); g.addColorStop(1,'rgba(255,0,0,0)');
      ctx.fillStyle=g; ctx.beginPath(); ctx.arc(b.sx,b.sy,9,0,Math.PI*2); ctx.fill();
      fc(b.sx,b.sy,5,K.RED);
    });
    const vis=blips.filter(b=>b.ok);
    if(vis.length){
      const cl=vis.reduce((a,b)=>a.dist<b.dist?a:b);
      const dStr=cl.dist<1000?`${Math.round(cl.dist)}mm`:`${(cl.dist/1000).toFixed(2)}m`;
      const spd=(0.25+0.15*Math.sin(t*0.025)).toFixed(2);
      ctxt(dStr,                        DP+CW/2,           DY+18,2,K.G);
      ctxt(`${cl.angle>=0?'+':''}${cl.angle.toFixed(0)}°`,DP+(CW+DP)+CW/2,DY+18,2,K.AMB);
      ctxt(`${spd}m/s`,                 DP+2*(CW+DP)+CW/2,DY+18,2,K.RED);
    } else {
      [DP+CW/2,DP+(CW+DP)+CW/2,DP+2*(CW+DP)+CW/2].forEach(x=>ctxt('--',x,DY+20,2,K.DIM));
    }
  }

  function tofCol(d) {
    if(d<=0)   return '#202020';
    if(d<300)  return '#FF0000';
    if(d<600)  {const f=(d-300)/300; return `rgb(248,${Math.round(f*80)},0)`;}
    if(d<1200) {const f=(d-600)/600; return `rgb(${Math.round(248*(1-f))},${Math.round(80+f*172)},0)`;}
    if(d<2500) return K.G;
    return K.DIM;
  }

  function drawTofGrid(t) {
    const CELL=30, GY=28;
    const cd=280+700*(0.5+0.5*Math.sin(t/110));
    for(let i=0;i<64;i++){
      const row=Math.floor(i/8),col=i%8;
      const dr_=row-3.5,dc_=col-3.5;
      const d=Math.max(50,Math.min(3000,cd+Math.sqrt(dr_*dr_+dc_*dc_)*230+Math.sin(i*17+t*0.08)*25));
      ctx.fillStyle=tofCol(d); ctx.fillRect(col*CELL+1,GY+row*CELL+1,CELL-2,CELL-2);
    }
  }

  function drawTofAngl(t) {
    const VIZ_CX=120, VIZ_CY=189;
    const ANGL_NUM_H=76, BTN_Y=236, BTN_H=44;
    const angleVal=(45+40*Math.sin(t*0.008)).toFixed(1);
    if(anglState===0){
      ctxt('POINT AT TARGET A',120,30,1,K.DIM);
      ctxt('--',120,44,4,K.DIM);
    } else if(anglState===1){
      ctxt('POINT AT TARGET B',120,30,1,K.AMB);
      ctxt(`${angleVal}`,120,44,4,K.AMB);
    } else {
      ctxt('ANGLE LOCKED',120,30,1,K.G);
      ctxt(`${angleVal}`,120,44,4,K.G);
    }
    function proj3(x,y,z){
      const rx=0.3,ry=t*0.01;
      const cx=Math.cos(rx),sx=Math.sin(rx),cy=Math.cos(ry),sy2=Math.sin(ry);
      const x2=x*cy+z*sy2, z2=-x*sy2+z*cy;
      const y2=y*cx-z2*sx, z3=y*sx+z2*cx;
      const sc=180/(z3+5);
      return [VIZ_CX+x2*sc, VIZ_CY+y2*sc];
    }
    const axLen=55;
    [[axLen,0,0,K.RED],[0,axLen,0,K.G],[0,0,axLen,K.DIM]].forEach(([x,y,z,c])=>{
      const p0=proj3(0,0,0), p1=proj3(x,y,z);
      lnC(p0[0],p0[1],p1[0],p1[1],c);
    });
    ctx.save(); ctx.font='8px "Courier New",monospace'; ctx.textBaseline='top'; ctx.fillStyle=K.RED; ctx.fillText('X',...proj3(axLen+4,0,0));
    ctx.fillStyle=K.G; ctx.fillText('Y',...proj3(0,axLen+4,0));
    ctx.fillStyle=K.DIM; ctx.fillText('Z',...proj3(0,0,axLen+4)); ctx.restore();
    const aAngle=0.8, p0=proj3(0,0,0), pA=proj3(Math.cos(aAngle)*50,Math.sin(aAngle)*50,0);
    lnC(p0[0],p0[1],pA[0],pA[1],K.G);
    fc(pA[0],pA[1],4,K.G);
    if(anglState>0){
      const bAngle=aAngle+parseFloat(angleVal)*Math.PI/180;
      const pB=proj3(Math.cos(bAngle)*50,Math.sin(bAngle)*50,0);
      lnC(p0[0],p0[1],pB[0],pB[1],K.AMB);
      fc(pB[0],pB[1],4,K.AMB);
      ctx.strokeStyle=anglState===2?K.G:K.AMB; ctx.lineWidth=1;
      ctx.beginPath();
      for(let s=0;s<=20;s++){
        const f=s/20, ang=aAngle+parseFloat(angleVal)*f*Math.PI/180;
        const pa=proj3(Math.cos(ang)*28,Math.sin(ang)*28,0);
        s===0?ctx.moveTo(pa[0],pa[1]):ctx.lineTo(pa[0],pa[1]);
      }
      ctx.stroke();
    }
    const bLabel=anglState===0?'LOCK A':anglState===1?'LOCK B':'RESET';
    const bCol=anglState===0?K.G:anglState===1?K.AMB:K.DIM;
    dr(20,BTN_Y,200,BTN_H,bCol); dr(22,BTN_Y+2,196,BTN_H-4,bCol);
    ctxt(`[ ${bLabel} ]`,120,BTN_Y+16,2,bCol);
  }

  function drawTofDist(t) {
    const DIST_VIZ_CX=120, DIST_VIZ_Y=64, DIST_VIZ_BOT=232;
    const DIST_BTN_Y=236, DIST_BTN_H=44, DIST_BTN_W=200, DIST_BTN_X=20;
    const dist=Math.round(500+1500*(0.5+0.5*Math.sin(t*0.008)));
    const distStr=dist<1000?`${dist}mm`:`${(dist/1000).toFixed(2)}m`;
    ctxt(distStr,120,4,4,K.G);
    const VH=DIST_VIZ_BOT-DIST_VIZ_Y, AX=DIST_VIZ_CX, AY=DIST_VIZ_BOT;
    const CLEN=VH;
    vl(AX,DIST_VIZ_Y,VH,K.DIM);
    const spread=52;
    lnC(AX,AY, AX+CLEN*Math.sin(spread*Math.PI/180), DIST_VIZ_Y, K.DIM);
    lnC(AX,AY, AX-CLEN*Math.sin(spread*Math.PI/180), DIST_VIZ_Y, K.DIM);
    const MAX_D=4000;
    [500,1000,1500,2000,3000,4000].forEach(ring=>{
      const yp=Math.round(AY-CLEN*ring/MAX_D);
      if(yp<DIST_VIZ_Y) return;
      const hw=Math.round(CLEN*Math.sin(spread*Math.PI/180)*ring/MAX_D);
      hl(AX-hw,yp,hw*2,K.FAINT);
      ctx.save(); ctx.fillStyle=K.DIM; ctx.font='7px "Courier New",monospace'; ctx.textBaseline='middle';
      ctx.fillText(ring>=1000?`${ring/1000}m`:`${ring}`,AX+hw+2,yp); ctx.restore();
    });
    const markerY=Math.round(AY-CLEN*Math.min(dist,MAX_D)/MAX_D);
    if(markerY>=DIST_VIZ_Y){
      const hw2=Math.round(CLEN*Math.sin(spread*Math.PI/180)*Math.min(dist,MAX_D)/MAX_D);
      ctx.strokeStyle=K.G; ctx.lineWidth=1; ctx.setLineDash([3,3]);
      ctx.beginPath(); ctx.moveTo(AX-hw2,markerY); ctx.lineTo(AX+hw2,markerY); ctx.stroke();
      ctx.setLineDash([]);
      fc(AX,markerY,4,K.G);
    }
    fr(AX-8,AY-6,16,6,K.DIM);
    dr(DIST_BTN_X,DIST_BTN_Y,DIST_BTN_W,DIST_BTN_H,K.G);
    dr(DIST_BTN_X+2,DIST_BTN_Y+2,DIST_BTN_W-4,DIST_BTN_H-4,K.G);
    ctxt('[ MEASURE ]',120,DIST_BTN_Y+16,2,K.G);
  }

  function drawTofNrml(t) {
    const NUM_H=52, VIZ_Y=80, VIZ_CX=120, VIZ_CY=180, SCALE=55;
    const tiltX=(12*Math.sin(t*0.007)).toFixed(1);
    const azimuth=(30+25*Math.sin(t*0.005)).toFixed(1);
    txt(`TILT ${tiltX} deg`,10,28,2,K.G);
    txt(`AZ ${azimuth} deg`,10,46,2,K.AMB);
    function proj(x,y,z){ return [VIZ_CX+(x+z*0.35)*SCALE/500, VIZ_CY+(y-z*0.18)*SCALE/500]; }
    [[500,0,0,K.RED],[0,500,0,K.G],[0,0,500,K.DIM]].forEach(([x,y,z,c])=>{
      const p0=proj(0,0,0), p1=proj(x,y,z);
      lnC(p0[0],p0[1],p1[0],p1[1],c);
    });
    for(let ri=0;ri<8;ri++) for(let ci=0;ci<8;ci++){
      const px_=(ci-3.5)*80, pz=(ri-3.5)*80;
      const py_=-px_*Math.sin(parseFloat(tiltX)*Math.PI/180)*0.3+Math.sin(t*0.05+ri*ci)*8;
      const [sx,sy]=proj(px_,py_,pz);
      ctx.fillStyle=K.DIM; ctx.fillRect(sx-1,sy-1,2,2);
    }
    const plCorners=[[-400,-20,-400],[-400,-20,400],[400,-20,400],[400,-20,-400]].map(([x,y,z])=>proj(x,y,z));
    ctx.strokeStyle=K.AMB; ctx.lineWidth=1; ctx.beginPath();
    ctx.moveTo(plCorners[0][0],plCorners[0][1]);
    plCorners.forEach(p=>ctx.lineTo(p[0],p[1]));
    ctx.closePath(); ctx.stroke();
    const tipP=proj(0,-350,0);
    lnC(VIZ_CX,VIZ_CY,tipP[0],tipP[1],K.G);
    fc(tipP[0],tipP[1],5,K.G);
  }

  function drawTof(t, tab) {
    fr(0,0,240,320,K.BG);
    drawHeader('TOF IMAGER');
    if(tab===0) drawTofGrid(t);
    else if(tab===1) drawTofAngl(t);
    else if(tab===2) drawTofDist(t);
    else drawTofNrml(t);
    drawTabBar(['GRID','ANGL','DIST','NRML'],tab);
  }

  function drawImuCube(t) {
    const CX=120,CY=154,SZ=62;
    const rx=t*0.012, ry=t*0.018, rz=t*0.007;
    const cos=Math.cos,sin=Math.sin;
    function rot([x,y,z]) {
      let nx=x,ny=y*cos(rx)-z*sin(rx),nz=y*sin(rx)+z*cos(rx);
      [nx,nz]=[nx*cos(ry)+nz*sin(ry),-nx*sin(ry)+nz*cos(ry)];
      [nx,ny]=[nx*cos(rz)-ny*sin(rz),nx*sin(rz)+ny*cos(rz)];
      return [nx,ny,nz];
    }
    const verts=[[-1,-1,-1],[-1,-1,1],[-1,1,-1],[-1,1,1],[1,-1,-1],[1,-1,1],[1,1,-1],[1,1,1]].map(v=>rot(v));
    const prj=v=>[CX+v[0]*SZ/(v[2]+4),CY+v[1]*SZ/(v[2]+4)];
    const edges=[[0,1],[0,2],[0,4],[1,3],[1,5],[2,3],[2,6],[3,7],[4,5],[4,6],[5,7],[6,7]];
    ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    edges.forEach(([a,b])=>{const pa=prj(verts[a]),pb=prj(verts[b]);ctx.beginPath();ctx.moveTo(pa[0],pa[1]);ctx.lineTo(pb[0],pb[1]);ctx.stroke();});
    ctx.strokeStyle=K.G;
    edges.slice(9).forEach(([a,b])=>{const pa=prj(verts[a]),pb=prj(verts[b]);ctx.beginPath();ctx.moveTo(pa[0],pa[1]);ctx.lineTo(pb[0],pb[1]);ctx.stroke();});
    hl(0,248,240,K.SEP);
    const roll=(Math.sin(t*0.012)*45).toFixed(1),pitch=(Math.sin(t*0.018)*30).toFixed(1),yaw=((t*0.007*180/Math.PI)%360).toFixed(1);
    ctxt(`R:${roll>=0?'+':''}${roll}`,60,253,1,K.G);
    ctxt(`P:${pitch>=0?'+':''}${pitch}`,120,253,1,K.AMB);
    ctxt(`Y:${parseFloat(yaw).toFixed(1)}`,180,253,1,K.DIM);
    ctxt('ROLL / PITCH / YAW',120,265,1,K.FAINT);
  }

  function drawImuPlmb(t) {
    const CX=120,CY=154,R=80,MD=66,BR=9;
    ctx.save(); ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    ctx.beginPath(); ctx.arc(CX,CY,R,0,Math.PI*2); ctx.stroke();
    ctx.beginPath(); ctx.arc(CX,CY,R-8,0,Math.PI*2); ctx.stroke();
    ctx.restore();
    for(let a=0;a<360;a+=30){
      const r=a*Math.PI/180;
      const ox=Math.cos(r),oy=Math.sin(r);
      lnC(CX+ox*(R-8),CY+oy*(R-8),CX+ox*R,CY+oy*R,K.DIM);
    }
    hl(CX-R+6,CY,2*(R-6)+1,K.DIM); vl(CX,CY-R+6,2*(R-6)+1,K.DIM);
    const bx=MD*0.35*Math.sin(t/95),by=MD*0.35*Math.cos(t/75);
    const level=Math.sqrt(bx*bx+by*by)<10;
    fc(Math.round(CX+bx),Math.round(CY+by),BR,level?K.G:K.RED);
    fc(Math.round(CX+bx)-3,Math.round(CY+by)-3,3,K.WHT);
    hl(0,248,240,K.SEP);
    const rollV=(bx/MD*40).toFixed(1),pitchV=(by/MD*40).toFixed(1);
    ctxt(`X: ${rollV>=0?'+':''}${rollV}°   Y: ${pitchV>=0?'+':''}${pitchV}°`,120,255,1,K.G);
    ctxt(level?'LEVEL':'TILTED',120,268,1,level?K.G:K.RED);
  }

  function tickScope(t) {
    _scopeBuf[0][_scopeHead]=Math.sin(t*0.012)*45;
    _scopeBuf[1][_scopeHead]=Math.sin(t*0.018+1.0)*30;
    _scopeBuf[2][_scopeHead]=(t*0.007*180/Math.PI)%360-180;
    _scopeHead=(_scopeHead+1)%SCOPE_SAMPLES;
  }

  function drawScopeFrame() {
    const SCOPE_Y0=46, LH=78;
    const LANES=[{lbl:'R',col:K.G},{lbl:'P',col:K.AMB},{lbl:'Y',col:K.DIM}];
    const RANGES=[90,60,180];
    hl(0,SCOPE_Y0+LH,240,K.FAINT);
    hl(0,SCOPE_Y0+LH*2,240,K.FAINT);
    [SCOPE_Y0+LH/2, SCOPE_Y0+LH+LH/2, SCOPE_Y0+LH*2+LH/2].forEach(my=>{
      hl(0,Math.round(my),240,K.FAINT);
    });
    LANES.forEach(({lbl,col},i)=>{
      fr(178,32+i*10,6,6,col);
      ctx.save(); ctx.fillStyle=col; ctx.font='8px "Courier New",monospace';
      ctx.textBaseline='top'; ctx.fillText(lbl,186,32+i*10-1); ctx.restore();
    });
    LANES.forEach(({col},li)=>{
      const RANGE=RANGES[li];
      const midY=SCOPE_Y0+li*LH+LH/2;
      ctx.strokeStyle=col; ctx.lineWidth=1; ctx.beginPath();
      for(let x=0;x<240;x++){
        const idx=(_scopeHead-240+x+SCOPE_SAMPLES)%SCOPE_SAMPLES;
        const v=_scopeBuf[li][idx];
        const y=midY - (v/RANGE)*(LH/2-3);
        x===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
      }
      ctx.stroke();
    });
  }

  function drawIMU(t, tab) {
    fr(0,0,240,320,K.BG);
    drawHeader('ATTITUDE',true);
    if(tab===0) drawImuCube(t);
    else if(tab===1) drawImuPlmb(t);
    else drawScopeFrame();
    drawTabBar(['CUBE','PLMB','SCPE'],tab);
  }

  function drawBattery(t) {
    fr(0,0,240,320,K.BG);
    drawHeader('BATTERY');
    const pct=Math.round(72+8*Math.sin(t/200));
    const col=pct>30?K.G:K.RED;
    ctxt('CHARGE LEVEL',120,58,1,K.DIM);
    const BX=10,BY=72,BW=196,BH=46,BR=5;
    ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    ctx.beginPath(); ctx.roundRect(BX,BY,BW,BH,BR); ctx.stroke();
    fr(206,86,8,18,K.DIM);
    const fillW=Math.round((BW-8)*pct/100);
    if(fillW>0){ ctx.save(); ctx.beginPath(); ctx.roundRect(BX+4,BY+4,BW-8,BH-8,BR-2); ctx.clip(); fr(BX+4,BY+4,fillW,BH-8,col); ctx.restore(); }
    ctxt('VOLTAGE',120,128,2,K.DIM);
    ctxt('3.84 V',120,146,4,K.G);
    ctxt('REMAINING',120,180,2,K.DIM);
    ctxt(`${Math.round(pct*18)}/1800 mAh`,120,198,2,K.G);
    hl(8,220,224,K.SEP);
    ctxt('CHARGE',120,228,2,K.DIM);
    ctxt(`${pct}%`,120,246,4,col);
  }

  function drawSettings() {
    fr(0,0,240,320,K.BG);
    drawHeader('SETTINGS');
    const ARROW_W=52, ROW_H=46, HDR_H=22;
    const sections=[
      {hdr:'DETECTION',  items:[['MAX RANGE','4000 MM','max detect dist'],['SENSITIVITY','MED','target filter level']]},
      {hdr:'GEOMETRY',   items:[['FOV ANGLE','55 DEG','radar sweep angle']]},
      {hdr:'DISPLAY',    items:[['BRIGHTNESS','100%','screen brightness'],['THEME','GREEN','color theme']]},
      {hdr:'POWER',      items:[['SLEEP TIME','60 SEC','idle sleep delay']]},
    ];
    let y=28;
    sections.forEach(sec=>{
      if(y+HDR_H>270) return;
      fr(0,y,240,HDR_H,K.BG);
      hl(0,y+HDR_H-1,240,K.AMB);
      ctxt(sec.hdr,120,y+6,1,K.AMB);
      y+=HDR_H;
      sec.items.forEach(([lbl,val,desc])=>{
        if(y+ROW_H>270) return;
        fr(0,y,240,ROW_H,K.BG);
        hl(0,y+ROW_H-1,240,K.SEP);
        vl(ARROW_W,y+2,ROW_H-4,K.SEP);
        vl(240-ARROW_W,y+2,ROW_H-4,K.SEP);
        ctxt('<',26,y+ROW_H/2-6,2,K.DIM);
        ctxt('>',240-26,y+ROW_H/2-6,2,K.DIM);
        txt(lbl,ARROW_W+8,y+6,1,K.DIM);
        txt(desc,ARROW_W+8,y+18,1,K.FAINT);
        ctxt(val,120,y+ROW_H/2-6,2,K.G);
        y+=ROW_H;
      });
    });
    const ry=270;
    dr(16,ry+7,208,26,K.RED);
    ctxt('RESET DEFAULTS',120,ry+14,2,K.RED);
  }

  const _mapPts=(function(){
    const pts=[]; const N=400; const ROOM=300;
    for(let i=0;i<N;i++){
      const u=(Math.random()-0.5)*2*ROOM, v=(Math.random()-0.5)*2*ROOM;
      const face=Math.floor(Math.random()*6);
      let p;
      if(face===0) p=[u,  ROOM,v];
      else if(face===1) p=[u,-ROOM,v];
      else if(face===2) p=[-ROOM,u,v];
      else if(face===3) p=[ ROOM,u,v];
      else if(face===4) p=[u,v,  ROOM];
      else              p=[u,v,-ROOM];
      pts.push(p);
    }
    return pts;
  })();

  function ironColor(v) {
    v=Math.max(0,Math.min(1,v));
    if(v<0.33)  { const f=v/0.33; return `rgb(${Math.round(f*200)},0,${Math.round(f*80)})`; }
    if(v<0.66)  { const f=(v-0.33)/0.33; return `rgb(${Math.round(200+f*55)},${Math.round(f*160)},${Math.round(80*(1-f))})`; }
    const f=(v-0.66)/0.34; return `rgb(255,${Math.round(160+f*95)},${Math.round(f*255)})`;
  }

  function drawMap3d(t) {
    fr(0,0,240,320,K.BG);
    drawHeader('3D MAP');
    const VIEW_Y=28, VIEW_H=244, VIEW_CX=120, VIEW_CY=150, FOCAL=200;
    const ry=t*0.006;
    const cosY=Math.cos(ry), sinY=Math.sin(ry);
    const projected=[];
    _mapPts.forEach(([px,py,pz])=>{
      const rx=px*cosY+pz*sinY, rz=-px*sinY+pz*cosY;
      const depth=rz+600;
      if(depth<10) return;
      const sx=VIEW_CX+rx*FOCAL/depth;
      const sy=VIEW_CY+py*FOCAL/depth;
      if(sy<VIEW_Y||sy>VIEW_Y+VIEW_H||sx<0||sx>240) return;
      projected.push({sx,sy,depth});
    });
    projected.sort((a,b)=>b.depth-a.depth);
    projected.forEach(({sx,sy,depth})=>{
      const v=1-Math.min(1,(depth-10)/900);
      ctx.fillStyle=ironColor(v);
      ctx.fillRect(Math.round(sx)-1,Math.round(sy)-1,2,2);
    });
    hl(8,272,224,K.SEP);
    fr(8,279,224,32,K.BG);
    dr(8,279,224,32,K.DIM);
    ctxt('CLEAR',120,289,2,K.DIM);
  }

  const SURF_COLS=['#00FFFF','#848484','#FF8000','#0000FF','#00FF00','#FF0000'];
  const SURF_NAMES=['CEILING','FLOOR','LEFT','RIGHT','FRONT','BACK'];
  const _survCap=[true,true,false,false,false,false];

  function drawSurveyor(t) {
    fr(0,0,240,320,K.BG);
    drawHeader('SURVEYOR');
    const INFO_Y=28, INFO_H=16;
    fr(0,INFO_Y,240,INFO_H,K.BG);
    ctxt('ROOM DIMENSIONS',120,INFO_Y+3,1,K.DIM);
    hl(0,INFO_Y+INFO_H-1,240,K.SEP);
    const BTN_Y=44, BTN_ROW_H=36;
    for(let i=0;i<6;i++){
      const col=i%2, row=Math.floor(i/2);
      const bx=col===0?0:120, bw=120, by=BTN_Y+row*BTN_ROW_H, bh=BTN_ROW_H;
      const sc=SURF_COLS[i], cap=_survCap[i];
      fr(bx,by,bw,bh,cap?'#0a0a0a':K.BG);
      dr(bx,by,bw,bh,cap?sc:K.DIM);
      ctx.save(); ctx.fillStyle=cap?sc:K.DIM; ctx.font='8px "Courier New",monospace';
      ctx.textBaseline='middle'; ctx.textAlign='center';
      ctx.fillText(SURF_NAMES[i],bx+bw/2,by+bh/2); ctx.restore();
    }
    const CLR_Y=152, CLR_H=24;
    dr(4,CLR_Y,140,CLR_H,K.G); ctxt('CAPTURE',74,CLR_Y+7,1,K.G);
    dr(152,CLR_Y,84,CLR_H,K.DIM); ctxt('CLEAR ALL',194,CLR_Y+7,1,K.DIM);
    hl(0,CLR_Y+CLR_H,240,K.SEP);
    const VIZ_Y=177, VIZ_CX=120, VIZ_CY=248, VIZ_H=143;
    fr(0,VIZ_Y,240,VIZ_H,K.BG);
    const W2=80,H2=50,D2=60;
    const corners=[
      [-W2,-H2,-D2],[ W2,-H2,-D2],[ W2, H2,-D2],[-W2, H2,-D2],
      [-W2,-H2, D2],[ W2,-H2, D2],[ W2, H2, D2],[-W2, H2, D2],
    ];
    const yaw=0.55+t*0.004, pitch=-0.4;
    const cy=Math.cos(yaw),sy2=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
    function projRoom(x,y,z){
      const x2=x*cy-z*sy2, z2=x*sy2+z*cy;
      const y2=y*cp-z2*sp, z3=y*sp+z2*cp;
      const FOCAL=220;
      return [VIZ_CX+x2*FOCAL/(z3+300), VIZ_CY+y2*FOCAL/(z3+300)];
    }
    const pts2d=corners.map(([x,y,z])=>projRoom(x,y,z));
    const wireEdges=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
    ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    wireEdges.forEach(([a,b])=>{
      if(pts2d[a][1]>VIZ_Y&&pts2d[b][1]>VIZ_Y){
        ctx.beginPath(); ctx.moveTo(pts2d[a][0],pts2d[a][1]); ctx.lineTo(pts2d[b][0],pts2d[b][1]); ctx.stroke();
      }
    });
    const userP=projRoom(0,0,0);
    fc(userP[0],userP[1],4,K.G);
  }

  function drawPower() {
    fr(0,0,240,320,K.BG);
    dr(2,2,236,316,K.RED); dr(4,4,232,312,K.RED);
    ctxt('POWER',120,55,4,K.RED);
    ctxt('OPTIONS',120,90,4,K.RED);
    dr(20,148,200,44,K.AMB); dr(22,150,196,40,K.AMB);
    ctxt('[ RESTART ]',120,162,2,K.AMB);
    ctxt('rescans all devices',120,185,1,K.FAINT);
    dr(20,204,200,44,K.RED); dr(22,206,196,40,K.RED);
    ctxt('[ POWER OFF ]',120,218,2,K.RED);
    ctxt('tap screen to wake',120,241,1,K.FAINT);
    dr(20,260,200,44,K.DIM); dr(22,262,196,40,K.DIM);
    ctxt('[ CANCEL ]',120,274,2,K.DIM);
  }

  function handleClick(x,y) {
    if(screen==='loading') return;
    if(screen==='menu'){
      if(x>=12&&x<=228&&y>=160&&y<=204)  { screen='radar';    t=0; lastScreen=''; return; }
      if(x>=8 &&x<=116&&y>=206&&y<=236)  { screen='map3d';    t=0; lastScreen=''; return; }
      if(x>=120&&x<=228&&y>=206&&y<=236) { screen='surveyor'; t=0; lastScreen=''; return; }
      if(x>=8 &&x<=116&&y>=238&&y<=264)  { screen='tof'; subTab=0; t=0; lastScreen=''; return; }
      if(x>=120&&x<=228&&y>=238&&y<=264) { screen='imu'; subTab=0; t=0; lastScreen=''; return; }
      if(x>=8 &&x<=116&&y>=266&&y<=290)  { screen='settings'; t=0; lastScreen=''; return; }
      if(x>=120&&x<=228&&y>=266&&y<=290) { screen='battery';  t=0; lastScreen=''; return; }
      if(x>=40&&x<=200&&y>=294&&y<=310)  { screen='power';    t=0; lastScreen=''; return; }
      return;
    }
    if(x>=3&&x<=67&&y>=3&&y<=25) { screen='menu'; t=0; lastScreen=''; return; }
    if(screen==='power'){
      if(x>=20&&x<=220&&y>=148&&y<=192) { screen='loading'; loadPct=0; t=0; lastScreen=''; return; } // RESTART
      if(x>=20&&x<=220&&y>=204&&y<=248) { screen='loading'; loadPct=0; t=0; lastScreen=''; return; } // POWER OFF
      if(x>=20&&x<=220&&y>=260&&y<=304) { screen='menu';    t=0; lastScreen=''; return; }            // CANCEL
      return;
    }
    if(screen==='tof'&&subTab===1&&y>=236&&y<=280){
      anglState=(anglState+1)%3; return;
    }
    if(screen==='tof'&&y>=280) { subTab=Math.min(3,Math.floor(x/60)); lastSubTab=-1; return; }
    if(screen==='imu'&&y>=280) { subTab=Math.min(2,Math.floor(x/80)); lastSubTab=-1; return; }
    if(screen==='map3d'&&x>=8&&x<=232&&y>=279&&y<=311) { t=0; return; }
  }

  canvas.addEventListener('click', e=>{
    const rect=canvas.getBoundingClientRect();
    handleClick((e.clientX-rect.left)*(240/rect.width),(e.clientY-rect.top)*(320/rect.height));
  });
  canvas.style.cursor='pointer';

  function loop() {
    // the card was closed: stop drawing to a canvas nobody can see
    if (!canvas.isConnected) { _esDemoRAF = null; return; }
    t++;
    if(screen==='loading'){
      loadPct=Math.min(100,loadPct+1.2);
      drawLoading();
      if(loadPct>=100) setTimeout(()=>{if(screen==='loading'){screen='menu';lastScreen='';}},300);
    } else if(screen==='menu'){
      if(lastScreen!=='menu'){ drawMenu(); lastScreen='menu'; }
    } else if(screen==='radar') {
      drawRadar(t);
    } else if(screen==='tof') {
      if(subTab===1) tickScope(t); // reuse scope buffer for ANGL animation
      drawTof(t,subTab);
      lastScreen='tof'; lastSubTab=subTab;
    } else if(screen==='imu') {
      if(subTab===2) tickScope(t);
      drawIMU(t,subTab);
      lastScreen='imu'; lastSubTab=subTab;
    } else if(screen==='battery') {
      drawBattery(t);
    } else if(screen==='settings') {
      if(lastScreen!=='settings'){ drawSettings(); lastScreen='settings'; }
    } else if(screen==='map3d') {
      drawMap3d(t);
    } else if(screen==='surveyor') {
      drawSurveyor(t);
    } else if(screen==='power') {
      if(lastScreen!=='power'){ drawPower(); lastScreen='power'; }
    }
    _esDemoRAF=requestAnimationFrame(loop);
  }
  loop();
}
