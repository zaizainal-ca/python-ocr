# python-ocr

This microservice is built using **FastAPI** and **PaddleOCR** to extract information from Malaysian identity cards (MyKad) and return it in a clean, structured JSON format. It is designed to be easily integrated into your main backend applications (such as Laravel).

---

## Prerequisites

- **Docker** & **Docker Compose** installed and running on your machine (e.g., OrbStack or Docker Desktop on macOS).

---

## Setup & Running the Project

1. **Open Docker** on your machine.
2. **Run the Container:**
   Open a terminal in the project directory (`/Users/newuser/rnd-things/paddleocr-test`) and run:
   ```bash
   docker compose up --build
   ```
3. **Access API Docs:**
   Once the container finishes building and is running, you can access the interactive API documentation (Swagger UI) at:
   - **http://localhost:6007/python-ocr/docs**

---

## API Documentation (Endpoints)

### 1. Health Check

- **Method:** `GET`
- **Path:** `/python-ocr/health`
- **Response:**
  ```json
  {
    "status": "healthy"
  }
  ```

### 2. OCR MyKad

- **Method:** `POST`
- **Path:** `/python-ocr/api/ocr/mykad`
- **Request (Multipart Form-Data):**
  - `file`: (MyKad image file, e.g., `myic.jpeg`)
- **Example Successful Response (JSON):**
  ```json
  {
    "success": true,
    "data": {
      "ic_number": "000000-00-0000",
      "name": "JOHN DOE ANAK RICHARD",
      "gender": "LELAKI",
      "religion": null,
      "citizenship": "WARGANEGARA",
      "state": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
      "address": [
        "123 JALAN AMPANG",
        "KUALA LUMPUR CITY CENTRE",
        "50450 KUALA LUMPUR",
        "WILAYAH PERSEKUTUAN KUALA LUMPUR"
      ]
    }
  }
  ```

---

## Laravel Integration Example

You can call this microservice from your Laravel controller using the Laravel HTTP Client (`Http` Facade).

### Example Code in Laravel Controller:

```php
use Illuminate\Support\Facades\Http;
use Illuminate\Http\Request;

public function processMyKadOcr(Request $request)
{
    // Ensure the request contains an image file
    if (!$request->hasFile('mykad_image')) {
        return response()->json(['error' => 'Please provide a MyKad image.'], 400);
    }

    $image = $request->file('mykad_image');

    try {
        // Send the file to the Python FastAPI Microservice
        $response = Http::attach(
            'file',
            file_get_contents($image->getRealPath()),
            $image->getClientOriginalName()
        )->post('http://localhost:6007/python-ocr/api/ocr/mykad');

        if ($response->successful()) {
            $ocrData = $response->json();

            if ($ocrData['success'] ?? false) {
                // Here you can save the data to the database or perform validation
                $mykadInfo = $ocrData['data'];

                return response()->json([
                    'status' => 'success',
                    'message' => 'OCR processed successfully!',
                    'data' => $mykadInfo
                ]);
            }
        }

        return response()->json([
            'status' => 'failed',
            'message' => 'Failed to process MyKad image.'
        ], 500);

    } catch (\Exception $e) {
        return response()->json([
            'status' => 'error',
            'message' => $e->getMessage()
        ], 500);
    }
}
```

---

## Deployment to AWS

Since this microservice is containerized using Docker, you can deploy it to AWS using one of the following options:

### Option 1: AWS ECS with AWS Fargate (Recommended for Production)

AWS Fargate is a serverless compute engine for containers.

1. **Push Image to AWS ECR (Elastic Container Registry):**
   - Create an ECR repository.
   - Authenticate your local Docker client:
     ```bash
     aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.<region>.amazonaws.com
     ```
   - Build the image:
     ```bash
     docker build -t paddleocr-api .
     ```
   - Tag and push the image to ECR:
     ```bash
     docker tag paddleocr-api:latest <aws_account_id>.dkr.ecr.<region>.amazonaws.com/paddleocr-api:latest
     docker push <aws_account_id>.dkr.ecr.<region>.amazonaws.com/paddleocr-api:latest
     ```
2. **Deploy on ECS Fargate:**
   - Create an ECS Cluster.
   - Create a Task Definition pointing to the ECR image (allocate at least 2 vCPUs and 4GB RAM since PaddleOCR requires sufficient memory).
   - Create an ECS Service under the cluster to launch your tasks, and optionally attach an Application Load Balancer (ALB).

### Option 2: AWS App Runner (Easiest & Managed)

AWS App Runner is a fully managed service that makes it easy to deploy containerized web applications.

1. Push your Docker image to private AWS ECR (following the steps in Option 1).
2. Go to the AWS App Runner console and click **Create Service**.
3. Select **Container Registry** and choose your ECR image.
4. Configure the port to `8000` and set resources (at least 2 vCPUs / 4GB RAM).
5. Deploy. App Runner will automatically handle routing, load balancing, and SSL.

### Option 3: AWS EC2 (Simple Virtual Machine)

1. Launch an EC2 instance (Ubuntu/Linux) with at least 4GB of RAM (e.g., `t3.medium`).
2. Install Docker on the instance:
   ```bash
   sudo apt-get update && sudo apt-get install docker.io -y
   ```
3. Ensure port `6007` is open in the EC2 instance's Security Group.

#### Jenkins CI/CD Automation (Deployment Automation)

You can use **Jenkins** to automate the build and deployment process to your EC2 server whenever there are code updates.

**Jenkins Configuration Steps:**

1. Create a new project of type **Freestyle project**.
2. In the **Source Code Management** section:
   - Select **Git**.
   - **Repository URL**: `https://github.com/zaizainal-ca/python-ocr.git`
   - **Credentials**: Add or select your GitHub credentials/token.
   - **Branch Specifier**: Set to `*/main` (instead of `*/master`).
3. In the **Build Steps** section, choose **Execute shell** and enter the following script:

   ```bash
   # 1. Ensure target directory exists on the EC2 server
   ssh ubuntu@$SERVER_IP "cd /home/ubuntu/; mkdir -p rp-cam-project"

   # 2. Sync project files to the target EC2 server via Rsync
   rsync -ravzg \
       --groupmap=*:www-data \
       --cvs-exclude \
       --delete-after \
       --exclude .vscode/ \
       --exclude .git/ \
       --exclude venv/ \
       --exclude __pycache__/ \
       -e ssh \
       ./ \
       ubuntu@$SERVER_IP:/home/ubuntu/rp-cam-project/rp-python-ocr/;

   # 3. Build and run the container using docker-compose on the UAT server
   ssh ubuntu@$SERVER_IP "cd /home/ubuntu/rp-cam-project/rp-python-ocr; \
           ROOT_PATH=/python-ocr docker compose up -d --build --force-recreate python-ocr; \
           docker image prune -f;"
   ```

#### Nginx Reverse Proxy Configuration
If you are running this microservice behind Nginx, you can route all API traffic under the `/python-ocr/` path to the container on port `6007`.

Add the following location block to your Nginx site configuration (e.g., `/etc/nginx/sites-available/default`):

```nginx
# ====================================
# python-ocr Microservice (PORT 6007)
# ====================================
location /python-ocr/ {
    proxy_pass http://127.0.0.1:6007/; # Trailing slash strips the '/python-ocr/' prefix

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Allow large image uploads for OCR processing
    client_max_body_size 20M; 
}
```

Test and reload Nginx to apply changes:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## Cost Estimation (Based on 1,000 requests/day)

PaddleOCR requires a minimum resource allocation of **2 vCPU and 4GB RAM** to ensure stable inference. Below is a monthly cost breakdown for running this workload at approximately **1,000 requests/day** (30,000 requests/month):

| AWS Service               | Compute Cost (Monthly)                                  | Extra Overhead (ALB, etc.)                 | Total Estimated Cost   | Pros/Cons                                                                                            |
| :------------------------ | :------------------------------------------------------ | :----------------------------------------- | :--------------------- | :--------------------------------------------------------------------------------------------------- |
| **AWS App Runner**        | **~$21.00**<br>(4GB RAM idle cost + active CPU billing) | None                                       | **~$21 - $23 / month** | **Best Value & Easiest**<br>+ Auto-scales CPU down when idle.<br>+ Free managed SSL & Load Balancer. |
| **AWS EC2** (`t3.medium`) | **~$30.00**<br>(24/7 flat rate)                         | None                                       | **~$30 / month**       | **Simple but unmanaged**<br>+ Very predictable pricing.<br>- You manage security patches and OS.     |
| **AWS ECS Fargate**       | **~$72.00**<br>(24/7 compute rate)                      | **~$22.00**<br>(Application Load Balancer) | **~$94 / month**       | **Enterprise Ready**<br>+ Multi-AZ high availability.<br>- Expensive for small scale.                |

### Cost Breakdown Details

#### 1. AWS App Runner Calculation

- **Active CPU Compute**: 1,000 requests \* 1.5s execution = 1,500 seconds (0.41 hours) per day. At $0.064/vCPU-hour: **negligible** (~$0.05/month).
- **Memory Allocation (Warm/Idle)**: 4 GB _ 730 hours/month _ $0.007/GB-hour = **$20.44**.
- **Request Fees**: 30,000 requests \* ($0.07 / 10,000 requests) = **$0.21**.

#### 2. AWS EC2 Calculation

- **t3.medium instance** (2 vCPU, 4GB RAM) running 24/7: 730 hours \* $0.0416/hour = **$30.36**.
- _Tip:_ Switching to an ARM64-based instance (like `t4g.medium`) reduces the cost to **~$24.50/month**.

#### 3. AWS ECS Fargate Calculation

- **Compute (24/7 Fargate Task)**: 2 vCPU ($59.10) + 4GB RAM ($12.98) = **$72.08**.
- **Load Balancer (ALB)**: A public-facing ALB adds a base charge of **~$22.26**.
