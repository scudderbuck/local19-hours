/* v143: app owner (admin in every chat room), pinned messages, mute (per room) and ban (all rooms).
   Pure helpers + static checks. The server side (Firestore rules) is tested in the emulator separately. */
const fs=require("fs"),A=require("assert"),path=require("path");
const file=process.argv[2]||path.join(__dirname,"index.html");
const html=fs.readFileSync(file,"utf8");
const sw=fs.readFileSync(path.join(path.dirname(file),"sw.js"),"utf8");
const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).map(s=>s.replace(/^<script>/,"").replace(/<\/script>$/,"")).sort((a,b)=>b.length-a.length)[0];
const m={exports:{}}; new Function("module",js)(m); const L=m.exports;
let pass=0,fail=0; const t=(n,f)=>{try{f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}};

t("version is v143 and the service worker cache name matches",()=>{
  A.strictEqual(L.APP_VERSION,"v143"); A.strictEqual(L.L19_BOOT_VER,"v143"); A.strictEqual(L.CACHE_VERSION,"l19hours-v143");
  A.ok(sw.includes('const C="l19hours-v143"')); A.ok(!sw.includes('const C="l19hours-v'+'142"'));
});
t("owner badge reads ADMIN · Longshore Life",()=>{A.strictEqual(L.OWNER_BADGE,"ADMIN · Longshore Life");A.ok(js.includes('<span class="rb o">\'+OWNER_BADGE+\'</span>'));});
t("modRole: owner is admin in every room, whatever the room role",()=>{
  A.strictEqual(L.modRole("member",true),"admin");A.strictEqual(L.modRole("moderator",true),"admin");A.strictEqual(L.modRole(undefined,true),"admin");
  A.strictEqual(L.modRole("moderator",false),"moderator");A.strictEqual(L.modRole("admin",false),"admin");A.strictEqual(L.modRole("owner",false),"member");A.strictEqual(L.modRole("",false),"member");
});
const act=o=>L.modActions(Object.assign({me:"me",uid:"them"},o));
t("member gets no moderation actions",()=>{A.deepStrictEqual(act({role:"member"}),[]);A.deepStrictEqual(act({role:"member",uid:"me"}),[]);});
t("moderator: mute/unmute others only, no pin, no ban",()=>{
  A.deepStrictEqual(act({role:"moderator"}),["mute"]);A.deepStrictEqual(act({role:"moderator",muted:true}),["unmute"]);
  A.deepStrictEqual(act({role:"moderator",uid:"me"}),[]);A.deepStrictEqual(act({role:"moderator",targetOwner:true}),[]);
});
t("room admin: pin + mute, no ban",()=>{A.deepStrictEqual(act({role:"admin"}),["pin","mute"]);A.deepStrictEqual(act({role:"admin",pinned:true}),["unpin","mute"]);A.deepStrictEqual(act({role:"admin",uid:"me"}),["pin"]);});
t("owner: pin + mute + ban everywhere (even with no room role)",()=>{
  A.deepStrictEqual(act({role:"member",owner:true}),["pin","mute","ban"]);
  A.deepStrictEqual(act({owner:true,pinned:true,muted:true,banned:true}),["unpin","unmute","unban"]);
  A.deepStrictEqual(act({owner:true,uid:"me"}),["pin"]);
});
t("nobody can mute or ban the owner (only pin their message)",()=>{A.deepStrictEqual(act({role:"admin",targetOwner:true}),["pin"]);A.deepStrictEqual(act({owner:true,targetOwner:true}),["pin"]);});
t("every action has a menu label",()=>{for(const k of ["pin","unpin","mute","unmute","ban","unban"])A.ok(L.MOD_LABEL[k],k);});
t("pinsFor: this channel only, newest first, at most 3",()=>{
  const p=[{id:"a",channel:"Ideas",text:"1",ms:1},{id:"b",channel:"Updates",text:"2",ms:9},{id:"c",channel:"Ideas",text:"3",ms:5},{id:"d",channel:"Ideas",text:"4",ms:3},{id:"e",channel:"Ideas",text:"5",ms:4},{id:"f",channel:"Ideas",text:"",ms:99},null];
  A.deepStrictEqual(L.pinsFor(p,"Ideas").map(x=>x.id),["c","e","d"]);A.deepStrictEqual(L.pinsFor(p,"Updates").map(x=>x.id),["b"]);A.deepStrictEqual(L.pinsFor(null,"Ideas"),[]);A.strictEqual(L.PIN_MAX,3);
});
t("pinDocOf: exactly the rule's keys (minus the server time) and within limits",()=>{
  const d=L.pinDocOf({text:"x".repeat(900),name:"Sam B. · L23",uid:"u1",channel:"Updates"},"me");
  A.deepStrictEqual(Object.keys(d).sort(),["by","channel","name","text","uid"]);A.strictEqual(d.text.length,500);A.strictEqual(d.channel,"Updates");A.strictEqual(d.by,"me");A.ok(d.name.length<=30);
  A.strictEqual(L.pinDocOf({text:"hi",name:"",uid:"u",channel:"Bogus"},"me").channel,"Ideas");A.strictEqual(L.pinDocOf({text:"hi",name:"",uid:"u"},"me").name,"?");
});
t("modDocOf: {name, by}, Coastwide local tag dropped, 1-30 chars",()=>{
  A.deepStrictEqual(L.modDocOf("Sam B. · L23","me"),{name:"Sam B.",by:"me"});A.deepStrictEqual(L.modDocOf("","me"),{name:"?",by:"me"});A.ok(L.modDocOf("x".repeat(80),"me").name.length<=30);
});
t("muted / banned notice is polite and says reading still works",()=>{
  A.strictEqual(L.muteNotice(false,false),"");A.ok(/muted you in this room/.test(L.muteNotice(true,false))&&/can read/.test(L.muteNotice(true,false)));
  A.ok(/all chat rooms/.test(L.muteNotice(false,true))&&/still read/.test(L.muteNotice(false,true)));A.strictEqual(L.muteNotice(true,true),L.muteNotice(false,true));
});
t("chat reads owners/{uid} once at load and uses the v143 Firestore paths",()=>{
  A.ok(js.includes('fs.getDoc(fs.doc(db,"owners",me))'));A.ok(js.includes('"rooms",code,"pins"'));A.ok(js.includes('"rooms",code,"muted",me'));A.ok(js.includes('f.doc(FB.db,"banned",t.uid)'));
  A.ok(!/setDoc\([^)]*"owners"/.test(js),"app never writes owners");
});
t("owner counts as admin for shared boards and merch (l19Fb.isAdmin)",()=>{A.ok(js.includes('isAdmin:()=>{const r=(roleMaps[bc()]||{})[uid()];return owner||(!!r&&r.role==="admin");}'));});
t("muted/banned can't send from the app either (send guard + disabled box)",()=>{A.ok(js.includes('if(mutedMe||bannedMe){err=muteNotice(mutedMe,bannedMe)'));A.ok(js.includes('g("chT").disabled=!!mn;g("chS").disabled=!!mn;'));});
t("no personal name, personal email, username or owner uid in the v143 code",()=>{
  const a=js.indexOf("v143: app owner"),b=js.indexOf("module.exports",a),seg=js.slice(a,b)+js.slice(js.indexOf("/* v143: owner + pins"),js.indexOf("function load()"))+js.slice(js.indexOf("/* v143: moderation */"),js.indexOf("/* v112: report sheet:"));
  A.ok(a>0&&seg.length>2000);for(const bad of [/scudderbuck/i,/daniel/i,/daniel white/i,/@gmail/i,/IuAjd5ILp2/])A.ok(!bad.test(seg),String(bad));
  A.ok(!html.includes("IuAjd5ILp2"),"owner uid is not in the public page");
});
console.log(pass+" passed, "+fail+" failed");process.exit(fail?1:0);
