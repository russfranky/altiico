var _____WB$wombat$assign$function_____=function(name){return (globalThis._wb_wombat && globalThis._wb_wombat.local_init && globalThis._wb_wombat.local_init(name))||globalThis[name];};if(!globalThis.__WB_pmw){globalThis.__WB_pmw=function(obj){this.__WB_source=obj;return this;}}{
let window = _____WB$wombat$assign$function_____("window");
let self = _____WB$wombat$assign$function_____("self");
let document = _____WB$wombat$assign$function_____("document");
let location = _____WB$wombat$assign$function_____("location");
let top = _____WB$wombat$assign$function_____("top");
let parent = _____WB$wombat$assign$function_____("parent");
let frames = _____WB$wombat$assign$function_____("frames");
let opener = _____WB$wombat$assign$function_____("opener");
const forwarderOrigin="https://web.archive.org/web/20221031160416/https://yetiverse.co/",onboardButton=document.getElementById("connectButton"),getAccountsButton=document.getElementById("getAccounts"),getAccountsResult=document.getElementById("getAccountsResult"),initialize=async()=>{const e=document.getElementById("connectButton"),t=()=>accounts&&accounts.length>0,n=()=>{const{ethereum:e}=window;return Boolean(e&&e.isMetaMask)},o=new MetaMaskOnboarding({forwarderOrigin:forwarderOrigin}),r=()=>{e.innerText="Onboarding in progress",e.disabled=!0,o.startOnboarding()},a=async()=>{try{c(await ethereum.request({method:"eth_requestAccounts"}))}catch(e){console.error(e)}};if(n()?(e.innerText="Connect with metamask",e.onclick=a,e.disabled=!1):(e.innerText="Click here to install MetaMask!",e.onclick=r,e.disabled=!1),n()){ethereum.autoRefreshOnNetworkChange=!1,ethereum.autoRefreshOnNetworkChange=!1,ethereum.on("accountsChanged",e=>{ethereum.request({method:"eth_getBlockByNumber",params:["latest",!1]}).then(e=>{handleEIP1559Support(void 0!==e.baseFeePerGas)}),c(e)});try{c(await ethereum.request({method:"eth_accounts"}))}catch(e){console.error("Error on init when getting accounts",e)}}function c(e){accounts=e,t()&&(window.location.href="https://web.archive.org/web/20221031160416/https://yetiverse.co/V3/setSession.php?address="+accounts)}};window.addEventListener("DOMContentLoaded",initialize);

}

/*
     FILE ARCHIVED ON 16:04:16 Oct 31, 2022 AND RETRIEVED FROM THE
     INTERNET ARCHIVE ON 20:03:08 Jul 19, 2026.
     JAVASCRIPT APPENDED BY WAYBACK MACHINE, COPYRIGHT INTERNET ARCHIVE.

     ALL OTHER CONTENT MAY ALSO BE PROTECTED BY COPYRIGHT (17 U.S.C.
     SECTION 108(a)(3)).
*/
/*
playback timings (ms):
  captures_list: 0.599
  exclusion.robots: 0.04
  exclusion.robots.policy: 0.028
  esindex: 0.01
  cdx.remote: 15.023
  LoadShardBlock: 259.899 (3)
  PetaboxLoader3.resolve: 98.447 (3)
  PetaboxLoader3.datanode: 114.927 (5)
  load_resource: 80.482
  loaddict: 24.702
*/