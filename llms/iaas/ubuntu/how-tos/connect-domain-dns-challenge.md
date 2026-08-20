Original link: https://docs.liara.ir/iaas/ubuntu/how-tos/connect-domain-dns-challenge/

# اتصال دامنه به سرور Ubuntu با روش DNS-01 Challenge

بر اساس مستندات رسمی [Let's Encrypt](https://letsencrypt.org/docs/challenge-types/?utm_source=liara.ir)، در روش DNS-01 Challenge مالکیت دامنه از طریق ایجاد یک رکورد TXT با نام `&lt;acme-challenge.&lt;domain_` در تنظیمات DNS تأیید می‌شود.  
پس از ثبت این رکورد، سرورهای Let's Encrypt آن را بررسی کرده و در صورت تطابق مقدار، گواهی SSL صادر می‌کنند.

مهم‌ترین مزیت DNS-01 نسبت به [HTTP-01 Challenge](https://docs.liara.ir/iaas/ubuntu/how-tos/connect-domain/)، این است که علاوه بر امکان صدور گواهی‌های Wildcard (مانند `example.com.*`)، برای دامنه‌هایی که وب‌سرور آن‌ها در اینترنت عمومی در دسترس نیست یا از چندین وب‌سرور و Load Balancer استفاده می‌کنند نیز به‌خوبی عمل می‌کند و وابسته به باز بودن پورت 80 یا قرار دادن فایل روی وب‌سرور نیست.  

در ادامه، روش اتصال دامنه به سرور مجازی اوبونتو با استفاده از روش DNS-01 Challenge، به صورت قدم‌به‌قدم، قرار گرفته است:  

## آموزش اتصال دامنه به سرور مجازی اوبونتو

۱. اضافه کردن دو رکورد `A` به سامانه مدیریت دامنه   

در ابتدا، بایستی دامنه خود را در یک سامانه مدیریت دامنه، مانند [Cloudflare](https://www.cloudflare.com/products/dns/?utm_source=liara.ir) یا [لیارا](https://liara.ir/products/dns/?utm_source=docs.liara.ir)، ثبت کنید. سپس،  
دو رکورد از نوع `A` با نام `@` و `www` و مقدار IP سرور مجازی ابری‌تان که در بخش **اتصال** سرور مجازی ابری در کنسول لیارا، قرار گرفته است؛ به آن، اضافه کنید.

[Video link](https://media.liara.ir/vps/add-cloud-server-ip-as-a-record-on-liara-dns-management-system.mp4)

۲. نصب وب‌سرور NginX  
پس از [اتصال به سرور مجازی ابری خود با استفاده از SSH](https://docs.liara.ir/iaas/ubuntu/how-tos/connect-to-server-using-ssh)، کافیست تا با اجرای دستور زیر، NginX را بر روی سرور خود، نصب کنید:

```bash
sudo apt update && sudo apt install -y nginx
```

۳. پیکربندی یک Virtual Host جدید  
با اجرای دستور زیر، یک فایل پیکربندی جدید ایجاد کنید (به جای `example.com`، نام دامنه خود را وارد کنید):

```bash
sudo nano /etc/nginx/sites-available/example.com
```

در ادامه، قطعه کد زیر را به فایل فوق، اضافه کنید (به جای `example.com`، نام دامنه خود را وارد کنید):

```config
server {
listen 80;
server_name example.com ;

root /var/www/example.com;
index index.html index.htm index.php;

location / {
    try_files $uri $uri/ =404;
}
}
```

سپس، برای ذخیره فایل و خروج از nano، دکمه‌های ترکیبی `CTRL + X` را فشرده و سپس `Y` را انتخاب کنید و در نهایت `Enter` را بزنید.  
در ادامه، یک دایرکتوری وب، ایجاد کنید (به جای `example.com`، نام دامنه خود را وارد کنید):

```bash
sudo mkdir -p /var/www/example.com
```

و یک فایل تست، به آن، اضافه کنید (به جای `example.com`، نام دامنه خود را وارد کنید):

```bash
echo '<h1>It works on Nginx!</h1>' | sudo tee /var/www/example.com/index.html
```

در ادامه، دسترسی‌های لازم را به فایل ایجاد شده، اعطا کنید (به جای `example.com`، نام دامنه خود را وارد کنید):

```bash
sudo chown -R www-data:www-data /var/www/example.com
```

پیکربندی ایجاد شده را، فعال کنید (به جای `example.com`، نام دامنه خود را وارد کنید):

```bash
sudo ln -s /etc/nginx/sites-available/example.com /etc/nginx/sites-enabled/
```

در نهایت، Nginx را، ری‌استارت کنید:

```bash
sudo systemctl restart nginx
```

۴. نصب گواهی SSL (با Let's Encrypt)  
با اجرای دستور زیر، پکیج `Certbot` را نصب کنید:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

در ادامه، دستور زیر را اجرا کنید تا Certbot یک گواهی SSL تهیه کند و `HTTP` را به `HTTPS`، ری‌دایرکت کند (به جای `example.com`، نام دامنه خود را وارد کنید):

```bash
sudo certbot --nginx -d example.com
```

۵. تنظیم تمدید خودکار SSL  
با اجرای دستور زیر، تمدید خودکار گواهی SSL را برای دامنه خود، تنظیم کنید:

```bash
sudo certbot renew --dry-run
```

۶. بررسی پیکربندی  
تمامی کارها، انجام شده است و اکنون، کافیست تا وب‌سرور خود را، ری‌استارت کنید:

```bash
sudo systemctl restart nginx
```

اکنون، می‌توانید در مرورگر، دامنه‌تان را وارد کنید تا به صفحه تستی که ساختید، هدایت شوید (به جای `example.com`، نام دامنه خود را وارد کنید):   

```js
https://example.com
```

در صورتی که صفحه سایت، با موفقیت، برایتان بالا آمد؛ بدین معناست که تمامی کارها  
را به درستی انجام داده‌اید و دامنه شما به سرور مجازی ابری‌تان، متصل شده است.

## all links

[All links of docs](https://docs.liara.ir/all-links-llms.txt)
