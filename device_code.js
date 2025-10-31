// 依赖：npm i sm-crypto
const {sm2} = require("sm-crypto");
const crypto = require("crypto");

// ========== arr（原始混淆数组） ==========
const arr = ["W4hdL8k5hHVdJG","mZe2mdaWuwXAvg1q","tmo6vfaRW53cU8kPW6VcVb8A","C3r1zgvUDc9JBg9JAY9qB3n0tMv3lMfJDgLVBG","mteYAvvoy1HA","EqNdSmoZW5ddRJ7cQG","vKjktCoh","CmoqamkxpWpdU0SCWOfyDCoR","gCkNdq9P","mteYndi3mNPerKvXEq","z1hdPH3cH8oZbXRdRCoaWQvnW57dOMq0W7j1W5SaWPrZWOabW4NcKrylca4fW5yjACktD3JdUSkDW5e","WQhdHmoxdq","W4ZcNmkKW7NcT8k0W74fW4qVzG","AM9PBG","mtq4mJq5mev4r3fQAq","mta1mZe1ntreDgvnywm","Bw9KzwW","W78pWPhdRHpdIKnQsSkJtSkuqmoT","nteWmZiWseLYDuri","FI8guZfeAv7cQf/dT07dH8ojnmoMW7m7hSoedXalwCkQkYNcRSkRWPdcJ0hcUNTIq1q","zg9fBMnYExb0","ywLKFf8","C3r1zgvUDc9IBg9Nl0jSB2CHC2f2zs5Hy3rPB24","cSkIbHXe","jbyroYu4W7balWpcNSk+BgS","zMLUza","mJa3BMDmwgPr","C3LZDgvT","hmkJaXjAWPK","WQiwWPdcP8oYa8kWWPBdThrQrhZdGCkBW4LrFmkuWOVdKdDssdnIW4tcSSkIWPZcSKyFfmoBWPCHW4eJzSkQWRldICo+WRz5WPvbW4vvz8khW4PNxeqjW7/cRCoAt3u","zSoLW6a","WQddOSozW6STW7JdKXfrfSkUW4BdVq","Aw5KzxHpzG","ndj1tMPPEuu","mheGdSog","EHhdPmoJW5pdRZJdQmkvwgtcN8oMvmoXoLxdPdLjWP/cT1tcPSk7","nti1mdrIANDtDfy","mdrHm2mZnwrLmdC1ytjLodzMmJHKntjHnde5odLHmdHLnZqWytGYzMi5nMq0m2q5ywy4ytu1mdLLmge0ztGZn2vJyJm4ngm0ngzLmwvLotvMnJaXzwyZnMyZyZG5mJiXngq0nwm5yJnMnZvIntC1nty0nJy4nZzHzdyWntjMmgyXzG","WO/dT2jaWQFcLq","WO8SW6VcMSkIW7RcIsiix1W","z2v0rgv2AwnLsw5MBW","zvpcM2FcIdKMbG8sbCokuq","W4ddM1PjW63dG8oLWQtdOSosWRxdNmk7W6OXW5RdOCoh","yNXF","WOddU8op","nCowaSkNW5O","aajEBCojW7H0kq","BgvUz3rO","B3bLBMLK","jmkkw8oxCKRcV2SaW6TDzSoYWQFcUCkfW6O6WQ/cQa"];

// ========== 混淆解码逻辑 ==========
const d = (() => {
    function decodeBase64(str) {
        if (!str) return "";
        const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/=";
        let buffer = "", result = "", t = 0, n, r = 0;
        for (let o = 0; o < str.length; o++) {
            n = chars.indexOf(str.charAt(o));
            if (~n) {
                t = r % 4 ? 64 * t + n : n;
                if (r++ % 4) buffer += String.fromCharCode(255 & (t >> ((-2 * r) & 6)));
            }
        }
        for (let i = 0; i < buffer.length; i++)
            result += "%" + ("00" + buffer.charCodeAt(i).toString(16)).slice(-2);
        return decodeURIComponent(result);
    }

    const cache = {};
    return (t) => {
        t = +t;
        if (cache[t] !== undefined) return cache[t];
        return (cache[t] = decodeBase64(arr[t]));
    };
})();

const g = (() => {
    const b64 = "=/+9876543210ZYXWVUTSRQPONMLKJIHGFEDCBAzyxwvutsrqponmlkjihgfedcba"
        .split("")
        .reverse()
        .join("");

    function decode(encoded) {
        if (!encoded) return "";
        let buffer = "", temp = 0, bitCount = 0;
        for (let i = 0; i < encoded.length; i++) {
            let n = b64.indexOf(encoded.charAt(i));
            if (~n) {
                temp = bitCount % 4 ? 64 * temp + n : n;
                if (bitCount++ % 4)
                    buffer += String.fromCharCode(255 & (temp >> ((-2 * bitCount) & 6)));
            }
        }
        try {
            return decodeURIComponent(
                buffer
                    .split("")
                    .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
                    .join("")
            );
        } catch {
            return buffer;
        }
    }

    function rc4(data, key) {
        const s = Array.from({length: 256}, (_, i) => i);
        let j = 0;
        for (let i = 0; i < 256; i++) {
            j = (j + s[i] + key.charCodeAt(i % key.length)) % 256;
            [s[i], s[j]] = [s[j], s[i]];
        }
        let i = 0;
        j = 0;
        let result = "";
        for (let c = 0; c < data.length; c++) {
            i = (i + 1) % 256;
            j = (j + s[i]) % 256;
            [s[i], s[j]] = [s[j], s[i]];
            const k = s[(s[i] + s[j]) % 256];
            result += String.fromCharCode(data.charCodeAt(c) ^ k);
        }
        return result;
    }

    const cache = {};
    return (t, key) => {
        t = +t;
        if (Object.prototype.hasOwnProperty.call(cache, t)) return cache[t];
        const decoded = decode(arr[t]);
        const decrypted = rc4(decoded, key);
        return (cache[t] = decrypted);
    };
})();

// ========== 一次性解混淆段 ==========
const SEGMENTS = (() => ({
    seg1: d(43, -26),
    seg2: d(21, -67),
    seg3: g(44, "W21%"),
    seg4: g(23, "pkZe"),
    seg5: g(45, "v3z6"),
    alphabet: g(29, "XbVS"),
}))();

// ========== 工具函数 ==========
function randStr(len = 16, chars = SEGMENTS.alphabet) {
    if (!chars || !chars.length)
        chars = "abcdefghijklmnopqrstuvwxyz0123456789";
    const L = chars.length;
    const buf = crypto.randomBytes(len);
    let out = "";
    for (let i = 0; i < len; i++) out += chars[buf[i] % L];
    return out;
}

// ========== 构建明文 ==========
function buildPlaintext(appId, device, randLen, ts) {
    const dev4 = [device.brand, device.model, device.system, device.platform].join(",");
    const constantTail = "ooru94khFi-GQMq4EnD0SCrrU4HU";
    const rand = randStr(randLen, SEGMENTS.alphabet);
    return `${SEGMENTS.seg1}${dev4}${SEGMENTS.seg2}${appId}${SEGMENTS.seg3}${ts}${SEGMENTS.seg4}${rand}${SEGMENTS.seg5}${constantTail}`;
}

// ========== SM2 加密入口 ==========
function fp(device) {
    const appId = "wx9f1c2e0bbc10673c"
    const randLen = 16
    const ts = Date.now()
    const pubKeyHex = "04a3c35de075a2e86f28d52a41989a08e740a82fb96d43d9af8a5509e0a4e837ecb384c44fe1ee95f601ef36f3c892214d45c9b3f75b57556466876ad6052f0f1f"
    const plaintext = buildPlaintext(appId, device, randLen, ts);
    return sm2.doEncrypt(plaintext, pubKeyHex, 1);
}

if (require.main === module) {
    process.stdin.setEncoding('utf8');

    let data = '';
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => {
        const obj = JSON.parse(data);
        // 调用并通过控制台传参
        console.log(fp(obj));
    });
}


