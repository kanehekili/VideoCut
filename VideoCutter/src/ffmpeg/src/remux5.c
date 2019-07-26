/*
 * MPEG/H264 muxer/cutter/trancoder
 * Copyright (c) 2018-2019 Kanehekili
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

/*
  * Versions supported: (libavutil/version.h)
  * ffmpeg 3.4.2
  * #define LIBAVCODEC_VERSION_MAJOR  57	 	
  * #define LIBAVCODEC_VERSION_MINOR 107
  * 
  * ffmpeg 4.x
  * #define LIBAVCODEC_VERSION_MAJOR  58
  * #define LIBAVCODEC_VERSION_MINOR 18
  */
#include <libavutil/timestamp.h>
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/opt.h>
#include <libavutil/frame.h>
#include <libavutil/mathematics.h>
#include <unistd.h>
#include <sys/sysinfo.h>
#include <stdio.h>

#if (LIBAVCODEC_VERSION_MAJOR == 57)
#define FFMPEG_REGISTER 1
#endif
#if (LIBAVCODEC_VERSION_MAJOR < 57)
#error "Ffmpeg 3.4 or newer is required"
#endif 
#define max(a,b) (a>b?a:b)
#define min(a,b) (a<b?a:b)
#define MODE_FAST 0
#define MODE_REMUX 1
#define MODE_DUMP 2
#define MODE_DUMPFRAMES 3

struct StreamInfo{
    int srcIndex; //Index of ifmt_ctx stream
    int dstIndex; //Index of out stream. TODO - currently 0: video, 1: audio
    AVStream *outStream;
    AVStream *inStream;
    AVCodecContext *in_codec_ctx; //Decode
    AVCodecContext *out_codec_ctx; //Encode
    AVOutputFormat *ofmt;
	AVRational in_time_base;
	AVRational out_time_base;
	double_t deltaDTS;//Time diff from one frame to another.
	int64_t frame_nbr; //count the frame number, since stream->nb_frames fails...
};

typedef struct {
    
    AVFormatContext *ifmt_ctx;
    AVFormatContext *ofmt_ctx;
    //int64_t frame_number;
    //int64_t gap; //sync cutting gaps
    int64_t video_sync_dts;// last transcoded video dts for audio sync
	int64_t streamOffset; //the offset between audio and video stream.
	int64_t audio_sync_dts; //Sync point audio for every scene
    double_t videoLen; //Approx duration in seconds
    int isDebug;
    int muxMode;
    char* sourceFile;
    char* targetFile;
    int nprocs; //Number of (hyper)threads
    short newCut;//indicates the first frame of a new cut.
} SourceContext;

typedef struct {
    int64_t start;
    int64_t end;
    int64_t pts;
    int64_t dts;
} CutData;

/*** globals ****/
    struct StreamInfo *videoStream;
    struct StreamInfo *audioStream;
    SourceContext context;

/*** Basic stuff ***/
double_t timeFromPTS(int64_t delta, AVRational time_base){
    double_t res = (double_t)delta*time_base.num/time_base.den;
    return res;
}

int64_t ptsFromTime(double_t ts,AVRational time_base){
    int64_t res = (int64_t)(ts*time_base.den/time_base.num);
    return res;
}
/*
static double get_fps(AVCodecContext *avctx) { //correct!
    return 1.0 / av_q2d(avctx->time_base) / FFMAX(avctx->ticks_per_frame, 1);
}
*/

static int findBestVideoStream(struct StreamInfo *info){//enum AVMediaType type
    info->srcIndex = av_find_best_stream(context.ifmt_ctx,AVMEDIA_TYPE_VIDEO,-1,-1,NULL,0);
    info->inStream=context.ifmt_ctx->streams[info->srcIndex];
    info->dstIndex=0; //May be a hack?
    info->in_time_base=info->inStream->time_base;
    return info->srcIndex;
}

static int findBestAudioStream(struct StreamInfo *info){
    info->srcIndex = av_find_best_stream(context.ifmt_ctx,AVMEDIA_TYPE_AUDIO,-1,-1,NULL,0);
    if (AVERROR_STREAM_NOT_FOUND == info->srcIndex){
        return -1;
    }
    if (AVERROR_DECODER_NOT_FOUND == info->srcIndex){
        av_log(NULL, AV_LOG_ERROR,"Err: No audio decoder found\n");
        return -1;
    }
    info->inStream=context.ifmt_ctx->streams[info->srcIndex];//TODO function in struct?
    info->dstIndex=1;//TODO more to come
    info->in_time_base=info->inStream->time_base;
    return info->srcIndex;
}

static int checkVideoFormat(struct StreamInfo *info){
   info->ofmt= NULL;
   int codecID = info->inStream->codecpar->codec_id;
   if (codecID == AV_CODEC_ID_MPEG2VIDEO){
        info->ofmt= av_guess_format("dvd", NULL, NULL);
        av_log(NULL, AV_LOG_INFO,"MPEG2 set to -f dvd\n");
    }else if(codecID == AV_CODEC_ID_VC1){//Matroska - we can't encode that
    	info->ofmt= av_guess_format("mp4", NULL, NULL);
    	av_log(NULL, AV_LOG_INFO,"Matroska set to h264\n");
    }
    return 1;
}


static void setupOutputParamters(struct StreamInfo *info, AVStream *outStream){
	AVCodecParameters *inCodecParm = info->inStream->codecpar;
	AVCodecParameters *outCodecParm = outStream->codecpar;

	outCodecParm->codec_type=inCodecParm->codec_type;
	outCodecParm->codec_id = context.ofmt_ctx->oformat->video_codec;
	//outCodecParm->codec_tag = ?;
	//outCodecParm->extradata;
	//outCodecParm->bits_per_coded_sample;
	//outCodecParm->profile;//z.B FF_PROFILE_H264_MAIN for H264
	//outCodecParm->level;
	outCodecParm->width=inCodecParm->width;
	outCodecParm->height=inCodecParm->height;
	outCodecParm->field_order = inCodecParm->field_order;
	outCodecParm->color_primaries = inCodecParm->color_primaries;
	outCodecParm->color_range= inCodecParm->color_range;
	outCodecParm->color_space = inCodecParm->color_space;
	outCodecParm->color_trc = inCodecParm->color_trc;
	outCodecParm->bit_rate = context.ifmt_ctx->bit_rate;
	outCodecParm->bits_per_coded_sample = inCodecParm->bits_per_coded_sample;

	/*
	 * parameters copy makes a mem copy of extra data...only, below
	 *  avcodec_parameters_to_context(AVCodecContext *codec,const AVCodecParameters *par):
 2055         par->format              = codec->pix_fmt;
 2056         par->width               = codec->width;
 2057         par->height              = codec->height;
 2058         par->field_order         = codec->field_order;
 2059         par->color_range         = codec->color_range;
 2060         par->color_primaries     = codec->color_primaries;
 2061         par->color_trc           = codec->color_trc;
 2062         par->color_space         = codec->colorspace;
 2063         par->chroma_location     = codec->chroma_sample_location;
 2064         par->sample_aspect_ratio = codec->sample_aspect_ratio;
 2065         par->video_delay         = codec->has_b_frames;

	if (inCodecParm->extradata){
		outCodecParm->extradata = av_mallocz(inCodecParm->extradata_size + AV_INPUT_BUFFER_PADDING_SIZE);
		if (outCodecParm->extradata){
			memcpy(outCodecParm->extradata, inCodecParm->extradata, inCodecParm->extradata_size);
			outCodecParm->extradata_size = inCodecParm->extradata_size;
		}
	}	 */

}


static int createOutputStream(struct StreamInfo *info){
    AVStream *out_stream;
    AVCodecParameters *pCodecParm = info->inStream->codecpar;

    out_stream = avformat_new_stream(context.ofmt_ctx, NULL);
    if (!out_stream) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed allocating output stream\n");
        return AVERROR_UNKNOWN;
    }

    /**
     * If the video codecs change (VC1 to h264), then parameter copy is NOT allowed/working
     */
    short sameCodec = (info->inStream->codecpar->codec_id == context.ofmt_ctx->oformat->video_codec);
    if (!sameCodec && pCodecParm->codec_type==AVMEDIA_TYPE_VIDEO && context.muxMode==MODE_REMUX){
    	av_log(NULL, AV_LOG_INFO,"Set output params manually\n");
    	setupOutputParamters(info,out_stream);
    }else {
		//Copy of stream params in case of same codec
		int ret = avcodec_parameters_copy(out_stream->codecpar, pCodecParm);
		if (ret < 0) {
			av_log(NULL, AV_LOG_ERROR,"Err: Failed to copy codec parameters\n");
			return ret;
		}
		out_stream->codecpar->codec_tag = 0;//if not m2t to mp4 fails

    }
    out_stream->start_time=AV_NOPTS_VALUE;
    out_stream->duration=0;
    out_stream->avg_frame_rate = info->inStream->avg_frame_rate;
    
    if (pCodecParm->codec_type==AVMEDIA_TYPE_AUDIO)
        out_stream->codecpar->frame_size = 2048;//TODO AAC: 1024*channels == 2048, mp3 =1152*channels =2304...

    info->outStream=out_stream;
    return 1;
}

int _initOutputContext(char *out_filename){
    AVFormatContext *ofmt_ctx = NULL; 
    AVOutputFormat *ofmt = NULL;
    int ret;
    
    ret= avformat_alloc_output_context2(&ofmt_ctx, videoStream->ofmt, NULL, out_filename);
    if (!ofmt_ctx || ret < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Could not create output context\n");
        return -1;
    }
 
    context.ofmt_ctx = ofmt_ctx;
    videoStream->ofmt = ofmt_ctx->oformat;    
    ofmt = ofmt_ctx->oformat;

    if ((ret = createOutputStream(videoStream))< 0){
        av_log(NULL, AV_LOG_ERROR,"Err: Could not create video output \n");
        return -1;
    }
    int64_t bitrate = context.ifmt_ctx->bit_rate;
    av_log(NULL, AV_LOG_INFO,"Video bitrate: %ld \n",bitrate);
    ofmt_ctx->bit_rate = bitrate;

    /* The VBV Buffer warning is removed: */
    AVCPBProperties *props;
    props = (AVCPBProperties*) av_stream_new_side_data(videoStream->outStream, AV_PKT_DATA_CPB_PROPERTIES, sizeof(*props));
    int64_t bit_rate = context.ifmt_ctx->bit_rate;

    props->buffer_size = 2024 *1024;
    props->max_bitrate = 3*bit_rate;
    props->min_bitrate = (2*bit_rate)/3;
    props->avg_bitrate = bit_rate;
    props->vbv_delay = UINT64_MAX;
     
    if (audioStream->srcIndex>=0) {
        if ((ret = createOutputStream(audioStream))< 0){
            av_log(NULL, AV_LOG_ERROR,"Err: Could not create video output \n");
            return -1;
        }
		int sampleRate = audioStream->inStream->codecpar->sample_rate;   
		bitrate = audioStream->inStream->codecpar->bit_rate;
		av_log(NULL, AV_LOG_INFO,"Audio: sample rate: %d bitrate: %ld\n",sampleRate,bitrate);
     }

    av_dump_format(ofmt_ctx, 0, out_filename, 1);

    if (!(ofmt->flags & AVFMT_NOFILE)) {
        ret = avio_open(&ofmt_ctx->pb, out_filename, AVIO_FLAG_WRITE);
        if (ret < 0) {
            av_log(NULL, AV_LOG_ERROR,"Err: Could not open output file '%s'", out_filename);
            return -1;
        }
     }


    ret = avformat_write_header(ofmt_ctx, NULL);
    if (ret < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Error occurred when opening output file\n");
        return -1;
    }

	videoStream->out_time_base=videoStream->outStream->time_base;
    if (audioStream->srcIndex >=0)
	   audioStream->out_time_base=audioStream->outStream->time_base;
    return 1;
}

int _setupStreams(SourceContext *sctx ){
    int ret;
    AVFormatContext *ifmt_ctx = NULL;
    char *in_filename = sctx->sourceFile;
    char *out_filename = sctx->targetFile;
    
    
    #ifdef FFMPEG_REGISTER
        av_register_all();
    #endif
    
    if ((ret = avformat_open_input(&ifmt_ctx, in_filename, 0, 0)) < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Could not open input file '%s'", in_filename);
        return -1;
    }

    if ((ret = avformat_find_stream_info(ifmt_ctx,NULL)) < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed to retrieve input stream information");
        return -1;
    }

    av_dump_format(ifmt_ctx, 0, in_filename, 0);
   
    context.ifmt_ctx = ifmt_ctx;
    //Later we take all audio streams.
    if ((ret = findBestVideoStream(videoStream)) < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: No video stream found \n");
        return -1;        
    }
    
    if ((ret = checkVideoFormat(videoStream))< 0){
        av_log(NULL, AV_LOG_ERROR,"Err: Failed to retrieve video format\n");
        return -1;        
    }
    
    if ((ret = findBestAudioStream(audioStream)) < 0)
      av_log(NULL, AV_LOG_INFO,"No audio stream found \n");

    return _initOutputContext(out_filename);
}

static int _initDecoder(struct StreamInfo *info){
    AVCodec *dec = NULL;
    AVCodecContext *dec_ctx = NULL;
    AVDictionary *opts = NULL;
    
    int ret;
    dec = avcodec_find_decoder(info->inStream->codecpar->codec_id);
    if (!dec) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed to find %s codec\n",av_get_media_type_string(AVMEDIA_TYPE_VIDEO));
        return -1;
    } 
    
    /* Allocate a codec context for the decoder */
    dec_ctx = avcodec_alloc_context3(dec);
    if (dec_ctx == NULL){
       av_log(NULL, AV_LOG_ERROR,"Err: Failed to alloc codec context\n");
       return -1;
    }
    avcodec_parameters_to_context(dec_ctx, info->inStream->codecpar);
    av_dict_set(&opts, "refcounted_frames","1",0);
    dec_ctx->framerate = av_guess_frame_rate(context.ifmt_ctx, info->inStream, NULL);
    //configure multi threading
    dec_ctx->thread_count=context.nprocs;
    dec_ctx->thread_type = FF_THREAD_FRAME | FF_THREAD_SLICE;
    av_log(NULL,AV_LOG_INFO,"Registered %d decoding threads \n",dec_ctx->thread_count);


    if ((ret=avcodec_open2(dec_ctx,dec,&opts))<0){ 
       av_log(NULL, AV_LOG_ERROR,"Err: Failed to open codec context\n");
       return -1;
    }
    info->in_codec_ctx=dec_ctx;
    return 1;
}

static int _initEncoder(struct StreamInfo *info, AVFrame *frame){
    AVCodec *encoder = NULL;
    AVCodecContext *enc_ctx = NULL;
    AVCodecContext *dec_ctx = NULL;
    AVDictionary *opts = NULL;
    int ret;
    encoder=avcodec_find_encoder(info->ofmt->video_codec);
    if (!encoder) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed to find %s out en-codec\n",av_get_media_type_string(AVMEDIA_TYPE_VIDEO));
        return -1;
    } 

    dec_ctx = info->in_codec_ctx;

    /* Allocate a codec context for the encoder - the dta should come from stream, not dec_ctx*/
    enc_ctx = avcodec_alloc_context3(encoder);
    if (enc_ctx == NULL){
       av_log(NULL, AV_LOG_ERROR,"Err: Failed to alloc out en-codec context\n");
       return -1;
    }
    //Most of the parameters should not be changed... No effect or even distortion.
    avcodec_parameters_to_context(enc_ctx,info->outStream->codecpar);
//    enc_ctx->height = dec_ctx->height;
//    enc_ctx->width = dec_ctx->width;
//    enc_ctx->bit_rate = context.ifmt_ctx->bit_rate;
    enc_ctx->sample_aspect_ratio = dec_ctx->sample_aspect_ratio;

    // take first format from list of supported formats 
    if (encoder->pix_fmts)
        enc_ctx->pix_fmt = encoder->pix_fmts[0];
    else
        enc_ctx->pix_fmt = dec_ctx->pix_fmt;
    // video time_base can be set to whatever is handy and supported by encoder !MUST!
    /*Setting of TB alters the bitrate:
     * 1/framerate: 39 mb
     * framerate 1001/24000
     * 1:90000 -> 1200 kb
     * 1:1000 ->3000 kb
     */

    enc_ctx->time_base = av_inv_q(dec_ctx->framerate);
    //enc_ctx->time_base = info->outStream->time_base;

    enc_ctx->framerate = dec_ctx->framerate;

	if (encoder->id == AV_CODEC_ID_H264){
     	enc_ctx->max_b_frames = dec_ctx->max_b_frames;
     	enc_ctx->ticks_per_frame=dec_ctx->ticks_per_frame;
		av_opt_set(enc_ctx->priv_data, "crf","23",0);
		//profile: baseline, main, high, high10, high422, high444
		av_opt_set(enc_ctx->priv_data, "profile", "main", 0);//more devices..
		av_opt_set(enc_ctx->priv_data, "preset", "medium", 0);

		//Bitrate section h264 -> if max then buffer -< but not reliably working with this codec!
		//enc_ctx->bit_rate = context.ifmt_ctx->bit_rate; ->copy params
		enc_ctx->rc_max_rate = context.ifmt_ctx->bit_rate;
		enc_ctx->rc_min_rate = (context.ifmt_ctx->bit_rate)/3;
		/*Basically, if you plan on encoding with CBR, you should limit the buffer to one second.
		 * That means the size = bitrate*seconds to buffer.
		 * The lower the buffer, the less the rate variance.
		 * https://streaminglearningcenter.com/blogs/book-excerpt-vbv-buffer-explained.html
		 * The VC1 decoder is broken ....
		 */
		if (dec_ctx->codec_id != AV_CODEC_ID_VC1)
			enc_ctx->rc_buffer_size= (int)(enc_ctx->rc_max_rate);

		//The lower the more bitrate....
		enc_ctx->qmin = 1;
		enc_ctx->qmax = 23;

     } else if (encoder->id == AV_CODEC_ID_MPEG2VIDEO){
        enc_ctx->max_b_frames = 2;
        enc_ctx->bit_rate = context.ifmt_ctx->bit_rate;
        enc_ctx->ticks_per_frame=2;

    /* The VBV Buffer warning comes because :
     * mpeg2 needs a VBV buffer, mp4 not.*/
    
        AVCPBProperties *props;
        props = (AVCPBProperties*) av_stream_new_side_data(info->outStream, AV_PKT_DATA_CPB_PROPERTIES, sizeof(*props));
        int64_t bit_rate = context.ifmt_ctx->bit_rate;
    
        props->buffer_size = 1024 *1024;
        props->max_bitrate = 4*bit_rate;
        props->min_bitrate = (2*bit_rate)/3;
        props->avg_bitrate = bit_rate;
        props->vbv_delay = UINT64_MAX;
      
    }else {
        enc_ctx->max_b_frames = 4;//What?
    }


    //configure multi threading
    enc_ctx->thread_count=context.nprocs;
    enc_ctx->thread_type = FF_THREAD_FRAME | FF_THREAD_SLICE;
    av_log(NULL,AV_LOG_INFO,"Registered %d encoding threads \n",enc_ctx->thread_count);
    
    if ((ret=avcodec_open2(enc_ctx,encoder,&opts))<0){ 
       av_log(NULL, AV_LOG_ERROR,"Err: Failed to open en-codec context\n");
       return -1;
    }

    ret = avcodec_parameters_from_context(info->outStream->codecpar, enc_ctx);
    if (ret < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Failed to copy encoder parameters to output stream \n");
        return ret;
    }   

    if (context.ofmt_ctx->oformat->flags & AVFMT_GLOBALHEADER){
        av_log(NULL, AV_LOG_INFO,"Using GLOBAL encode headers\n");
        enc_ctx->flags |= AV_CODEC_FLAG_GLOBAL_HEADER; 
    }

    if (context.ofmt_ctx->oformat->flags & AVFMT_VARIABLE_FPS){
    	av_log(NULL, AV_LOG_INFO,"Detected VAR FPS\n");
    }

    frame->format = info->in_codec_ctx->pix_fmt;
    frame->width = info->in_codec_ctx->width;
    frame->height = info->in_codec_ctx->height;

    info->out_codec_ctx=enc_ctx;
    return 1;
}

/**************** MUXING SECTION ***********************/
static int seekTailGOP(struct StreamInfo *info, int64_t ts,CutData *borders) {
    AVPacket pkt;
    int64_t lookback=ptsFromTime(10.0,info->inStream->time_base); //go 10 seconds back in time
    int timeHit=0;
    int keyFrameCount=0;
    int maxFrames=3;
    int64_t maxPTS =0;
    int64_t gop[3]={0,0,0};

    if (lookback > ts)
        lookback=0;
     av_init_packet(&pkt);
    if(av_seek_frame(context.ifmt_ctx, info->srcIndex, ts-lookback, AVSEEK_FLAG_BACKWARD) < 0){
        av_log(NULL, AV_LOG_ERROR,"Err: av_seek_frame failed.\n");
        return -1;
    }
   
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
       if (pkt.stream_index != info->srcIndex){
            av_packet_unref(&pkt); 
            continue;
        }    
        int i;
        if (pkt.flags == AV_PKT_FLAG_KEY){
            for (i =0; i< maxFrames-1; i++){
                gop[i]=gop[i+1];
            }
            gop[maxFrames-1]=pkt.dts;
            keyFrameCount++;
            if (timeHit)
                break;
        } 
        if (pkt.dts >= ts && !timeHit){
            timeHit=1;
            borders->dts=pkt.dts;
            borders->pts=pkt.pts;
        }
        if (pkt.dts <= ts && !timeHit){
        	maxPTS=max(maxPTS,pkt.pts);
        }
        av_packet_unref(&pkt); 
    }

    av_packet_unref(&pkt); 
    int idx=0;
    int t1 = abs(ts - gop[1]);
    int t2 = abs(ts - gop[2]);
    if (t1 > t2){
        idx++;
    }
    borders->start=gop[idx];
    borders->end=gop[idx+1];
    AVRational time_base = info->in_time_base;
    int64_t vStreamOffset = info->inStream->start_time;    
    double_t st = av_q2d(time_base)*(ts-vStreamOffset);
    double_t g0 = av_q2d(time_base)*(gop[idx]-vStreamOffset);
    double_t g1 = av_q2d(time_base)*(gop[idx+1]-vStreamOffset);
    av_log(NULL, AV_LOG_VERBOSE,"Tail: (keycount %d block: %d) deltas: %d/%d Searchkey:%ld (%.3f) Start:%ld (%.3f) > End: %ld (%.3f) (cutpoint pts:%ld dts:%ld, max:%ld) \n",keyFrameCount,idx,t1,t2,ts,st,borders->start,g0,borders->end,g1,borders->pts,borders->dts,maxPTS);
    return 1;

}

//seeking only the video stream head
static int seekHeadGOP(struct StreamInfo *info, int64_t ts,CutData *borders) {
    AVPacket pkt;
    int64_t lookback=ptsFromTime(1.0,info->in_time_base);
    int timeHit=0;
    int keyFrameCount=0;
    int maxFrames=3;
    int64_t gop[3]={0,0,0};

    if (lookback > ts)
        lookback=ts;
    //const int genPts= context.ifmt_ctx->flags & AVFMT_FLAG_GENPTS; alway 0->so packet buffer is used
    av_init_packet(&pkt);
    if(av_seek_frame(context.ifmt_ctx, info->srcIndex, ts-lookback, AVSEEK_FLAG_BACKWARD) < 0){
        av_log(NULL, AV_LOG_ERROR,"Err: av_seek_frame failed.\n");
        return -1;
    }
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
       if (pkt.stream_index != info->srcIndex){
            av_packet_unref(&pkt); 
            continue;
        }    
        int i;
        if (pkt.flags == AV_PKT_FLAG_KEY){
            for (i =0; i< maxFrames-1; i++){
                gop[i]=gop[i+1];
            }
            gop[maxFrames-1]=pkt.dts;
            keyFrameCount++; 
            if (timeHit && keyFrameCount>1)//one gop == 2 frames are needed
                break;
        } 
        
        if (pkt.dts >= ts && !timeHit){
            timeHit=1;
            borders->dts=pkt.dts;
            borders->pts=pkt.pts;
        }
        av_packet_unref(&pkt); 
    }

    av_packet_unref(&pkt); 
    int idx=0;
    int t1 = abs(ts - gop[0]);
    int t2 = abs(ts - gop[1]);
    if (t2 < t1){
        idx++;
    }
    borders->start=gop[idx];
    borders->end=gop[idx+1];
    AVRational time_base = info->in_time_base;
    int64_t vStreamOffset = videoStream->inStream->start_time;
    double_t st = av_q2d(time_base)*(ts-vStreamOffset);
    double_t g0 = av_q2d(time_base)*(gop[idx]-vStreamOffset);
    double_t g1 = av_q2d(time_base)*(gop[idx+1]-vStreamOffset);
    av_log(NULL, AV_LOG_VERBOSE,"Head:(keycount %d block: %d) deltas: %d/%d Searchkey:%ld (%.3f) start:%ld (%.3f) > End: %ld (%.3f) (cutpoint-dts:%ld) \n",keyFrameCount,idx,t1,t2,ts,st,borders->start,g0,borders->end,g1,borders->dts);
    return keyFrameCount<4;
}
/** Write packet to the out put stream. Here we calculate the PTS/dts. Only Audio and video streams are incoming  **/
static int write_packet(struct StreamInfo *info,AVPacket *pkt){
        AVStream *in_stream = NULL, *out_stream = NULL;
        char frm='*';
        int isVideo = videoStream->srcIndex==pkt->stream_index;

        if (isVideo) {
            //context.frame_number+=1;
            if (pkt->flags == AV_PKT_FLAG_KEY){
              frm='I';
            }
            else
                frm='v';      
        }
        in_stream  = info->inStream;
        out_stream  = info->outStream;

        /**
         * Cutting data is in video time. Convert it from video time to stream time.
         * To have a zero based dts without gaps the follwing rule is applied:
         * dts-(cumulated gaps + dts of the start of first cut - the stream offset between video and audio)
         * The offset prevents too many negative TS at the start of the stream that lies behind timewise
         * It is the difference between video and the "latest" audio in DTS.
        */ 

        int64_t currentDTS = info->outStream->cur_dts; //out-time
 
        //control time /audio sync
            //int64_t	cum =  context.gap+context.video_first_dts - context.streamOffset;
            //int64_t offset = av_rescale_q(context.streamOffset,videoStream->inStream->time_base, in_stream->time_base);
            //int64_t in_DTS = max(pkt->dts - offset,0); //intime - no negative dts on remux
            //dts - headofGOP - delta time AV... 
            //int64_t out_DTS = av_rescale_q(in_DTS,in_stream->time_base, out_stream->time_base);

        //remove early audio packets.... crucial!
        //sync -x = sound later/delayed.
        //x only for TRANSCODE
        if (!isVideo && (pkt->dts < context.audio_sync_dts)){
            double_t currTS = av_q2d(out_stream->time_base)*context.audio_sync_dts;
            double_t audioTS = av_q2d(out_stream->time_base)*pkt->dts;
            int64_t euqiv = av_rescale_q(pkt->dts,in_stream->time_base,videoStream->inStream->time_base);
            double_t equivTS = av_q2d(videoStream->inStream->time_base)*euqiv;
			av_log(NULL, AV_LOG_VERBOSE,"Drop early packet: %c: dts:%ld (%.3f) Equiv D:%ld (%.3f) sync:%ld (%.3f)\n",frm,pkt->dts,audioTS,euqiv,equivTS,context.audio_sync_dts,currTS);
			av_packet_unref(pkt);
			return 1;
		}

        if (currentDTS == AV_NOPTS_VALUE){
        	currentDTS=0;
//        	if (!isVideo && context.muxMode==MODE_REMUX)
//        		currentDTS=+av_rescale_q(2*videoStream->deltaDTS,videoStream->outStream->time_base, out_stream->time_base);

        }


        /* save original packet dates*/
        int64_t p1 = pkt->pts;
        int64_t d1 = pkt->dts;
        int64_t delta = p1-d1;
        int64_t dur = pkt->duration;

        pkt->stream_index = info->dstIndex;
        pkt->pos=-1;//File pos is unknown if cut..

        //remux workaround ... duration may be 0 ->next pts - curr pts... will not work if pts invalid
        if (dur==0  && isVideo){
		   dur=info->deltaDTS;
		   //pkt->dts=round(info->deltaDTS*info->frame_nbr);
		   pkt->dts = currentDTS+(int64_t)dur;
		   context.video_sync_dts=pkt->dts;//needed by trailing audio
        }else {
        	pkt->duration = av_rescale_q(dur, in_stream->time_base, out_stream->time_base);
			//increment the DTS instead of calculating it.
 		   if (context.newCut && context.muxMode==MODE_REMUX && !isVideo){//GAP handling! - mp2 incompatible
// 			  int64_t vdts=videoStream->outStream->cur_dts;
// 			 int64_t pdts= max(currentDTS,vdts + 2*videoStream->deltaDTS);
//
// 			  currentDTS = av_rescale_q(pdts,videoStream->outStream->time_base,out_stream->time_base);
// 			 av_log(NULL, AV_LOG_VERBOSE,"*GAP* CurrDTS was: %ld, now: %ld v-PTS:%ld\n",out_stream->cur_dts,currentDTS,pdts);
 			  context.newCut=0;
 			  //TEST -makes it better. So by default audio is a little behind....
 			 //currentDTS += 5*pkt->duration;
 		   }
 		   pkt->dts = currentDTS+pkt->duration;
        }

        if (p1!=AV_NOPTS_VALUE)
		   pkt->pts = pkt->dts+delta;

        double_t dtsCalcTime = av_q2d(out_stream->time_base)*(pkt->dts);
        int ts = (int)dtsCalcTime;
        int hr = (ts/3600);
        int min =(ts%3600)/60;
        int sec = (ts%60)%60;  
        
        if (isVideo && !context.isDebug){
            double_t progress = (dtsCalcTime/context.videoLen)*100;
            av_log(NULL, AV_LOG_INFO,"%ld D:%.2f %02d:%02d.%02d %.2f%%\n",info->frame_nbr,dtsCalcTime,hr,min,sec,progress);
        }
        if (context.isDebug){
            double_t ptsCalcTime = av_q2d(out_stream->time_base)*(pkt->pts);
            double_t orgDTSTime= av_q2d(in_stream->time_base)*(d1);
            double_t orgPTSTime = av_q2d(in_stream->time_base)*(p1);
            char other=isVideo?'A':'V';
            int64_t cv = isVideo? av_rescale_q(d1,info->inStream->time_base,videoStream->inStream->time_base):av_rescale_q(d1,info->inStream->time_base,audioStream->inStream->time_base);
            double_t otherInTime = isVideo?av_q2d(videoStream->inStream->time_base)*cv:av_q2d(audioStream->inStream->time_base)*cv;
        	av_log(NULL, AV_LOG_VERBOSE,"%ld,%c:P:%ld (%ld-%.3f) D:%ld (%ld %c:%ld T:%.3f %c:%.3f) Pt:%.3f Dt:%.3f dur %ld (%ld) delta: %ld size: %d flags: %d curr:%ld\n",info->frame_nbr,frm,pkt->pts,p1,orgPTSTime,pkt->dts,d1,other,cv,orgDTSTime,other,otherInTime,ptsCalcTime,dtsCalcTime,pkt->duration,dur,delta,pkt->size,pkt->flags,currentDTS);
        }
        int ret = av_interleaved_write_frame(context.ofmt_ctx, pkt);
        if (ret < 0) {
            av_log(NULL, AV_LOG_ERROR,"Err: Error muxing packet\n");
            return ret;
        }
        info->frame_nbr++;//Only if really written
        av_packet_unref(pkt);
        return 1;
        
}

//Plain muxing, no encoding yet.Expect an Iframe first
static int mux1(CutData head,CutData tail){
    struct StreamInfo *streamInfo;
    AVPacket pkt = { .data = NULL, .size = 0 };
    int fcnt =0;
    av_init_packet(&pkt);
    int64_t audioTail = audioStream->inStream? av_rescale_q(tail.end,videoStream->inStream->time_base, audioStream->inStream->time_base):0;
    short audioAtEnd = audioTail==0;
    short videoAtEnd = 0;
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
        int streamIdx = pkt.stream_index;
        int isVideo = streamIdx == videoStream->srcIndex;
        int isAudio = streamIdx == audioStream->srcIndex;
        if (isVideo){
            char frm='v';
            streamInfo = videoStream;
            if (pkt.flags == AV_PKT_FLAG_KEY){
                fcnt=1;
                frm='I';
            }
            //ignore leading and trailing video packets. 
            if (fcnt==0 ){
                av_log(NULL,AV_LOG_VERBOSE,"Skip head packet %ld [%c]\n",pkt.dts,frm);
                av_packet_unref(&pkt);
                continue;
            }
            if (pkt.dts >=tail.end){
              if (audioAtEnd)
                 break;
               else {
                av_log(NULL,AV_LOG_VERBOSE,"Skip tail packet %ld [%c]\n",pkt.dts,frm);
                av_packet_unref(&pkt);
                videoAtEnd=1;
                continue;
               }
            }
              
        } else if (isAudio ) {
            streamInfo = audioStream;
            //run audio until it reaches tail.end as well
            
            if (pkt.dts >= audioTail){
                if (videoAtEnd)
                  break;
                else {
                av_packet_unref(&pkt);
                av_log(NULL,AV_LOG_VERBOSE,"Skip tail packet %ld [*]\n",pkt.dts);
                audioAtEnd=1;
                continue;
              }
		    }
        } else {
          av_packet_unref(&pkt);
          continue; //No usable packet.
        }  

        write_packet(streamInfo,&pkt);
    }
    av_packet_unref(&pkt);
    av_interleaved_write_frame(context.ofmt_ctx, NULL);//flushing
    return 1;
}

static int decode(AVCodecContext *dec_ctx,AVPacket *pkt,AVFrame *frame){
   
    int ret = avcodec_send_packet(dec_ctx, pkt);
    if (ret < 0) {
        av_log(NULL, AV_LOG_ERROR,"Err: Error sending a packet for decoding\n");
        return ret;
    }
    ret = avcodec_receive_frame(dec_ctx, frame);
    if (ret == AVERROR(EAGAIN)){ //Output not available - send a new input
        return -1;
    }
    if (ret == AVERROR_EOF){
        av_log(NULL, AV_LOG_ERROR,"Err: Error receiving a decoded frame\n");
        return -2;
    }
    return ret;
    
}

//find offset correction: Take the first I Frame

static int64_t seekPrimaryOffset(struct StreamInfo *info){
    AVPacket pkt;
    int64_t first_dts = 0;
    
     av_init_packet(&pkt);
     if(av_seek_frame(context.ifmt_ctx, info->srcIndex,0, AVSEEK_FLAG_BACKWARD) < 0){
        av_log(NULL, AV_LOG_ERROR,"Err: av_seek_frame failed.\n");
        return -1;
    }
    
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
       if (pkt.stream_index != info->srcIndex){
            av_packet_unref(&pkt); 
            continue;
        }
        if (pkt.flags == AV_PKT_FLAG_KEY ){
            first_dts = pkt.dts;
            break;
        }
        av_packet_unref(&pkt); 
    }
    av_packet_unref(&pkt); 
    
    avcodec_flush_buffers(info->in_codec_ctx);
    
    return first_dts;
}

static int flushFrames(struct StreamInfo *info, AVFrame *frame){
    int ret;
    if((ret = avcodec_send_packet(info->in_codec_ctx, NULL))>=0){
        while (ret >=0){
            ret = avcodec_receive_frame(info->in_codec_ctx,frame);
            if (ret==0){
                if (frame->flags & AV_FRAME_FLAG_DISCARD){
                    av_log(NULL,AV_LOG_INFO,"frame will be discarded: %ld\n",frame->pts);
                    continue;
                }
                int ret2;
                ret2=avcodec_send_frame(info->out_codec_ctx,frame);
                if (ret2==0){
                    av_log(NULL, AV_LOG_VERBOSE,"flush Frame sent: P:%ld dur:%ld\n",frame->pts,frame->pkt_duration);
                    AVPacket enc_pkt;
                    enc_pkt.data = NULL;
                    enc_pkt.size = 0;
                    av_init_packet(&enc_pkt);
                    int ret3 =0;
                    while (ret3 >=0){
                        ret3=avcodec_receive_packet(info->out_codec_ctx,&enc_pkt);
                        if (ret3 ==0){
                            av_log(NULL, AV_LOG_VERBOSE,"f->");
                            enc_pkt.stream_index=info->inStream->index;//compatibility
                            write_packet(info,&enc_pkt);
                        }
                    }
                }else {
                    av_log(NULL, AV_LOG_ERROR,"Err: -Frame error %d\n",ret2);
                }
            }
        }
    }
    return 1;
}

static int flushPackets(struct StreamInfo *info){
    AVPacket pkt;
    int ret;
    if (!info->out_codec_ctx)
        return 1;
    pkt.data = NULL;
    pkt.size = 0;
    av_init_packet(&pkt);
    av_log(NULL, AV_LOG_VERBOSE,"Flush packets\n");
    if((ret = avcodec_send_frame(info->out_codec_ctx, NULL))>=0){
        while (ret >=0){
            ret = avcodec_receive_packet(info->out_codec_ctx,&pkt);
            if (ret==0){
                av_log(NULL, AV_LOG_VERBOSE,"p->");
                pkt.stream_index=info->inStream->index;//compatibility
                write_packet(info,&pkt);
            }else {
                av_packet_unref(&pkt);
                if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF)
                    av_log(NULL, AV_LOG_VERBOSE,"Flush packet-Queue empty\n");
                else 
                    av_log(NULL, AV_LOG_ERROR,"Err: Flush packet-receive error:%d\n",ret);
             }
        }
    }
    
    avcodec_free_context(&info->out_codec_ctx);
    return 1;
}
/**
 * After frames have been transcoded we not more autio frames to write
 */
static int pushTailAudio(struct StreamInfo *info, int64_t start, int64_t stop){
    AVPacket pkt;
    if (!audioStream->inStream)
    	return 1;
    int64_t audioTail = av_rescale_q(context.video_sync_dts,videoStream->outStream->time_base, audioStream->outStream->time_base);
    int64_t counter = info->outStream->cur_dts;


    av_init_packet(&pkt);

    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
        int isAudio = pkt.stream_index == audioStream->srcIndex;
        if (!isAudio){
        	av_packet_unref(&pkt);
        	continue;
        }
       	//if (pkt.dts > audioTail){
        counter+=av_rescale_q(pkt.duration,info->inStream->time_base,info->outStream->time_base);
        if (counter > audioTail){
      		av_log(NULL,AV_LOG_VERBOSE,"Audio tail (P:%ld) %ld of:%ld\n", pkt.pts,counter,audioTail);
   			av_packet_unref(&pkt);
   			break;
        }
        double_t outtime= av_q2d(info->outStream->time_base)*(pkt.dts);
        double_t intime= av_q2d(info->inStream->time_base)*(pkt.dts);
        av_log(NULL,AV_LOG_VERBOSE,"** P/D:%ld in:%.3f out:%.3f cnt:%ld\n",pkt.dts,intime,outtime,counter);
        write_packet(audioStream,&pkt);//unreffed there
    }
    return 1;
}

static int transcode(struct StreamInfo *info, int64_t start, int64_t stop){
    AVPacket pkt;
    int keyFrameCount=0;
    int ret;
    int gopsize=0;
    AVFrame *frame;
    int64_t check_pts=0;

    frame = av_frame_alloc();    
    ret = _initEncoder(info,frame);
    if (ret <0)
        return -1; 
    
    av_init_packet(&pkt);
        
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {
        int isVideo = pkt.stream_index == videoStream->srcIndex;
        int isAudio = pkt.stream_index == audioStream->srcIndex;
        
        if (isAudio){
//        	if (pkt.dts <= audioTail)
//        		write_packet(audioStream,&pkt);
//        	else
//        		av_log(NULL, AV_LOG_VERBOSE,"**Tail: %ld of:%ld\n",pkt.pts,audioTail);
    		write_packet(audioStream,&pkt);
        	continue;

        } else if (isVideo) {
            if (pkt.flags == AV_PKT_FLAG_KEY){
                keyFrameCount++;
                av_log(NULL, AV_LOG_VERBOSE,"GOP: %d\n",gopsize);
                gopsize=0;
            }
        }else {
            //unusable packet
            av_packet_unref(&pkt);
            continue;
        }
            
        gopsize++;
        double_t dtime= av_q2d(info->inStream->time_base)*(pkt.dts);//Instream time...
        if ((ret = decode(info->in_codec_ctx,&pkt,frame))<0) {
            av_log(NULL, AV_LOG_VERBOSE,"Buffer pkt: isKey:%d p:%ld d:%ld [%.3f] dur:%ld\n",pkt.flags, pkt.pts,pkt.dts,dtime,pkt.duration);
        }else {
        	//either PTS or DTS ..
        	if (frame->pts == AV_NOPTS_VALUE)
        		check_pts = frame->best_effort_timestamp;//works -not on h264 raw/mkv
        	else
        		check_pts = frame->pts;

            char ptype = av_get_picture_type_char(frame->pict_type);
            double_t fptime= av_q2d(info->inStream->time_base)*(frame->pts);
            //DTS is always==PTS- since its decoded...
            av_log(NULL, AV_LOG_VERBOSE,"[%d]%d) decode key: %d (%d) type: %c, pts: %ld time: %.3f frm dur %ld, pkt dur:%ld",keyFrameCount,info->in_codec_ctx->frame_number,frame->key_frame,pkt.flags,ptype,frame->pts,fptime,frame->pkt_duration,pkt.duration);
            
			if (frame->pts != AV_NOPTS_VALUE && frame->pts < start){
				av_log(NULL, AV_LOG_VERBOSE,"- Ignore\n");
				av_packet_unref(&pkt);
				continue;
			}else if (check_pts > stop){
				av_log(NULL, AV_LOG_VERBOSE,"- End of GOP: %ld\n",frame->pts);
				break;
			}

            //try to encode
            ret = av_frame_make_writable(frame);
            if (ret<0){
                av_log(NULL, AV_LOG_ERROR,"Err: frame not writable\n");
                av_packet_unref(&pkt);
                continue;
            }
            frame->pict_type = AV_PICTURE_TYPE_NONE;                               
            ret=avcodec_send_frame(info->out_codec_ctx,frame);
            if (ret== AVERROR_EOF)
                av_log(NULL, AV_LOG_VERBOSE,"-Error EOF\n");
            else if (ret==AVERROR(EINVAL))
                av_log(NULL, AV_LOG_VERBOSE,"-Error EINVAL\n");
            else if (ret==AVERROR(EAGAIN))
                av_log(NULL, AV_LOG_VERBOSE,"-Error EAGAIN\n");
            else if (ret==0){
                av_log(NULL, AV_LOG_VERBOSE,"+\n");
                AVPacket enc_pkt={ .data = NULL, .size = 0 };
                av_init_packet(&enc_pkt);
                while (avcodec_receive_packet(info->out_codec_ctx,&enc_pkt)>=0){
                    enc_pkt.stream_index=info->inStream->index;//compatibility
                    write_packet(info, &enc_pkt);//will unref package...
                }
            }    
            else
                av_log(NULL, AV_LOG_ERROR,"Err: -Frame error %d\n",ret);
        }
        
        av_packet_unref(&pkt);     
    }
    av_packet_unref(&pkt);     
    flushFrames(info,frame);
    flushPackets(info);
    info->out_codec_ctx=NULL;
    avcodec_flush_buffers(info->in_codec_ctx);
    av_frame_free(&frame);
    pushTailAudio(audioStream,start,stop);
    return 1;
}


/** decode the input stream, display its data **/
static int dumpDecodingData(){
    struct StreamInfo *streamInfo;
	char frm;
    AVPacket pkt;
    AVFrame *frame;
    
    pkt.data = NULL;
    pkt.size = 0;
    av_init_packet(&pkt); 
    frame = av_frame_alloc(); 
    
    while (av_read_frame(context.ifmt_ctx, &pkt)>=0) {

        int isVideo = videoStream->srcIndex==pkt.stream_index;
        if (isVideo) {
            streamInfo = videoStream;
            if (pkt.flags == AV_PKT_FLAG_KEY)
                frm='I';      
            else
                frm='v';      
        }else {//Audio
            frm='*';        
            streamInfo = audioStream;
        }		
        int64_t streamOffset = streamInfo->inStream->start_time;
        double_t dtsCalcTime = av_q2d(streamInfo->outStream->time_base)*pkt.dts;
        double_t ptsCalcTime = av_q2d(streamInfo->outStream->time_base)*pkt.pts;
        double_t xxx = av_q2d(streamInfo->inStream->time_base)*(pkt.dts-streamOffset);
        
        av_log(NULL, AV_LOG_INFO,"%ld [%c] P:%ld  D:%ld Pt:%.3f Dt:%.3f Time:%.3f size:%d dur:%ld flags:%d\n",streamInfo->outStream->nb_frames,frm,pkt.pts,pkt.dts,ptsCalcTime,dtsCalcTime,xxx,pkt.size,pkt.duration,pkt.flags);

        if (isVideo && context.muxMode==MODE_DUMPFRAMES) {
            int ret;
            if ((ret = decode(streamInfo->in_codec_ctx,&pkt,frame)) == 0) {
                char ptype = av_get_picture_type_char(frame->pict_type);
                double_t fptime= av_q2d(streamInfo->outStream->time_base)*(frame->pts - streamInfo->inStream->start_time);  
                //DTS is always==PTS- since its decoded...
                av_log(NULL, AV_LOG_INFO,"%d)FRM key: %d(%d) type:%c,pts:%ld time:%.3f\n",streamInfo->in_codec_ctx->frame_number,frame->key_frame,pkt.flags,ptype,frame->pts,fptime);
            }else {
                double_t dtime= av_q2d(streamInfo->outStream->time_base)*(pkt.dts - streamInfo->inStream->start_time);  
                av_log(NULL, AV_LOG_INFO,"Buffer pkt: isKey:%d p:%ld d:%ld [%.3f]\n",pkt.flags, pkt.pts,pkt.dts,dtime);            
            }
        }

          av_packet_unref(&pkt);
    }
    av_frame_free(&frame);
    return 1;                
}
/** seek to the timeslots and cut them out **/
static int seekAndMux(double_t timeslots[],int seekCount){
    AVRational time_base = videoStream->in_time_base;
    AVRational framerate = videoStream->in_codec_ctx->framerate;
    int64_t vStreamOffset = 0;
    int64_t aStreamOffset = 0;
    if (audioStream->inStream){
    	aStreamOffset= audioStream->inStream->start_time;
        vStreamOffset = videoStream->inStream->start_time;
    }
    int64_t startOffset = vStreamOffset - aStreamOffset;
    int64_t mainOffset = (vStreamOffset<aStreamOffset)?aStreamOffset:vStreamOffset;
    double_t streamOffsetTime = av_q2d(time_base)*startOffset;
    double_t vStreamStartTime = av_q2d(time_base)*vStreamOffset;
    double_t aStreamStartTime = av_q2d(audioStream->in_time_base)*aStreamOffset;
    double_t mainOffsetTime = av_q2d(time_base)*mainOffset;
    int64_t duration = videoStream->inStream->duration;
    int res =0;

    double_t fps = (double_t)framerate.num/framerate.den;//same as get_fps
    videoStream->deltaDTS = (videoStream->out_time_base.den/fps);
    
    CutData headBorders;
    CutData tailBorders;
    
    //Correction for seeking
    int64_t first_dts = max(seekPrimaryOffset(videoStream),0);
    int64_t zeroDTS = first_dts-vStreamOffset;
    double_t zeroTime= av_q2d(time_base)*zeroDTS;

    av_log(NULL, AV_LOG_INFO,"Mux video - Offset: %ld (%.3f) fps: %.3f audio -offset %ld (%.3f) delta:%ld (%.3f)\n",vStreamOffset,vStreamStartTime,fps,aStreamOffset,aStreamStartTime,startOffset,streamOffsetTime);
    av_log(NULL, AV_LOG_INFO,"First IFrame DTS found: %ld, normalized: %ld (%.3f) mainOffset: %ld (%.3f)\n",first_dts,zeroDTS,zeroTime,mainOffset,mainOffsetTime);
    av_log(NULL, AV_LOG_INFO,"Video tbi: %d tbo: %d ; Audio tbi: %d tbo: %d \n",time_base.den,videoStream->out_time_base.den,audioStream->in_time_base.den,audioStream->out_time_base.den);
    av_log(NULL, AV_LOG_INFO,"Video IN: %s long:%s\n",context.ifmt_ctx->iformat->name,context.ifmt_ctx->iformat->long_name);
    if (context.ofmt_ctx)
        av_log(NULL, AV_LOG_INFO,"Video OUT: %s long:%s\n",context.ofmt_ctx->oformat->name,context.ofmt_ctx->oformat->long_name);

    context.streamOffset = startOffset; 
    context.newCut=0;
    audioStream->frame_nbr=0;
    videoStream->frame_nbr=0;
    
    if (context.muxMode >= MODE_DUMP){
        res = dumpDecodingData();
        return res;
    }
    
    //int64_t prevTail =0;
	//int64_t gap =0;
    int i;
    for (i = 0; i < (seekCount); ++i){
        double_t startSecs = timeslots[i];
        double_t endSecs = timeslots[++i];
        if (endSecs < startSecs)
            endSecs=startSecs+duration;
            
        int64_t ptsStart = ptsFromTime(startSecs+mainOffsetTime+zeroTime,time_base);
        int64_t ptsEnd = ptsFromTime(endSecs+mainOffsetTime+zeroTime,time_base);
        av_log(NULL, AV_LOG_INFO,"************************\nSearch from %.3f to %.3f pts: %ld - %ld \n",startSecs,endSecs,ptsStart,ptsEnd);
        seekHeadGOP(videoStream,ptsStart,&headBorders);//Header GOP
        seekTailGOP(videoStream,ptsEnd,&tailBorders); //TAIL GOP
//        int64_t head = (context.muxMode == MODE_REMUX)?headBorders.dts:headBorders.start;


//        if (i==1){
//			prevTail=head;
//		}
//        int64_t deltaGap= head-prevTail;
//		gap += deltaGap;
//        context.gap = gap;
//        av_log(NULL, AV_LOG_INFO,"Gap calc <tail %ld head: %ld gap: %ld [%ld] delta calc:%.3f\n",prevTail,head,context.gap,deltaGap,videoStream->deltaDTS);
//        prevTail = (context.muxMode == MODE_REMUX)?tailBorders.dts:tailBorders.end;
        
        if (headBorders.start == headBorders.end || tailBorders.start==tailBorders.end){
            av_log(NULL, AV_LOG_ERROR,"Err: Seek times out of range. Aborted");
            return -1;
        }
        
         if(av_seek_frame(context.ifmt_ctx, videoStream->srcIndex, headBorders.start, AVSEEK_FLAG_ANY) < 0){
            av_log(NULL, AV_LOG_ERROR,"Err: av_seek_frame failed.\n");
            return -1;
        }
        avcodec_flush_buffers(videoStream->in_codec_ctx);
        //Start of an I frame we are.
        
        if (context.muxMode == MODE_REMUX){
        	if (audioStream->inStream){
        		//Guess
        		int64_t gap = (int64_t)videoStream->deltaDTS*2;
        		context.audio_sync_dts= av_rescale_q( headBorders.dts-gap,videoStream->inStream->time_base, audioStream->inStream->time_base);
        	}
            res = transcode(videoStream,headBorders.dts,tailBorders.dts);
            context.newCut=1;
        }
        else {
        	if (audioStream->inStream)
        		context.audio_sync_dts= av_rescale_q( headBorders.start,videoStream->inStream->time_base, audioStream->inStream->time_base);
            res = mux1(headBorders,tailBorders);
        }
        if ( res < 0){
            av_log(NULL, AV_LOG_ERROR,"Err: muxing/transcode failed\n");
            return -1;
        }
    }
    return 1;    
}

int calculateVideoLen(double_t timeslots[],int seekCount){
    double_t duration = 0.0;
    int i;
    for (i = 0; i < (seekCount); ++i){
        double_t startSecs = timeslots[i];
        double_t endSecs = timeslots[++i];
        if (endSecs > startSecs)
            duration += (endSecs - startSecs);
        
    }
    av_log(NULL, AV_LOG_INFO,"Video length is about %3.2f seconds\n",duration);
    return duration;
}

/******************** Main helper *************************/
void usage(char *arg){
        printf("usage: %s -i input output -s time,time,time,time.....\n"
               "Remux a media file with libavformat and libavcodec.\n"
               "The output format is guessed according to the file extension.\n"
               "\t-s: Set the time in seconds.millis for start & stop of a chunk\n"
               "\t-r: Transcode the parts. This is really slow currently! Don't use it\n"
               "\t-d: debug mode\n"
               "\t-l: decode & list all packets (no cutting)\n"
               "\t-lf: decode & list all packets & frames (no cutting)\n"
               "\n"
               "\tExample:\n"
               "\t./remux5 /home/xxx/Videos/File.m2t /home/xxx/Videos/Cut.mp4 -s 386.080,415.760,510.460,529.320\n"
               "\n"
               "will mux the frames between 386 - 415 and 510 - 529 seconds. So the times describe which parts you want in the target. \n"
               "\n", arg);
}

int parseArgs(int argc, char *argv[],double_t array[]) {
  int c,i, count;
  opterr = 0;
  count=0;
  char *tmp;
  while ((c = getopt (argc, argv, "?s:drl:i:")) != -1){
        switch (c){
          case 's':
              i = 0;
              
              tmp = strtok(optarg,",");
              while (tmp != NULL) {
                array[i++]= atof(tmp);
                tmp = strtok(NULL,","); 
              }
              count=i;
              break;
          case 'd':
            av_log_set_level(AV_LOG_VERBOSE);//DEBUG IS TOO verbose
            context.isDebug=1;
            break;
          case 'r':
            context.muxMode=MODE_REMUX;
            break;
          case 'l':
            tmp = strtok(optarg,"");
            context.muxMode=MODE_DUMP;                
            if (tmp[0]=='f')
                context.muxMode=MODE_DUMPFRAMES;
            else
                optind--;    
            break;
          case 'i':
            context.sourceFile=strtok(optarg,"");
            break;            
          case '?':
            usage(argv[0]);
            return -1;
          default:
            printf("that dont work\n");
            return -1;
         }
    }
  
    if (optind < argc){
        context.targetFile = argv[optind];
    }
    return count; 
}
static int shutDown(int ret){
    AVOutputFormat *ofmt = NULL;
    AVFormatContext *ofmt_ctx = NULL;
    free(videoStream);
    free(audioStream);
    ofmt_ctx = context.ofmt_ctx;
    if (ofmt_ctx == NULL) {
        return ret;
    }

    ofmt = ofmt_ctx->oformat;
     /* close input */
    avformat_close_input(&context.ifmt_ctx);
     /* close output */
    if (ofmt_ctx && !(ofmt->flags & AVFMT_NOFILE))
        avio_closep(&ofmt_ctx->pb);
    avformat_free_context(ofmt_ctx);
    
    if (ret != 0 && ret != AVERROR_EOF) {
        av_log(NULL, AV_LOG_ERROR,"Err: Error occurred: %s\n", av_err2str(ret));
        return 1;
    }
    av_log(NULL, AV_LOG_INFO,"*Done*\n");
    return 0;
}


/****************** MAIN **************************/
int main(int argc, char **argv)
{
    double_t timeslots[255];
    int seekCount;
    int ret;

	videoStream = malloc(sizeof(*videoStream));
    audioStream = malloc(sizeof(*audioStream));
    context.isDebug=0;
    context.muxMode = MODE_FAST;
    context.sourceFile = NULL;
    context.targetFile = NULL;

    
    if (argc < 3) {
        usage(argv[0]);
        return 1;
    }

    context.nprocs = get_nprocs();

    //The seeks slots...
    seekCount = parseArgs(argc,argv,timeslots);
    if (seekCount <0)
        return shutDown(EINVAL);

    if (context.sourceFile == NULL || context.targetFile == NULL){
        av_log(NULL, AV_LOG_ERROR,"Err: No file given!\n");
        return shutDown(ENOENT); 
    }

    printf("Args: %s -> %s \n",context.sourceFile,context.targetFile);

    if ((ret=_setupStreams(&context))<0)
        return shutDown(1);
        
    if (videoStream->srcIndex>=0){
          _initDecoder(videoStream);
    }
    /** ENTER MUX **/
    context.videoLen = calculateVideoLen(timeslots,seekCount);
    ret=seekAndMux(timeslots,seekCount);

    if (ret)
        av_write_trailer(context.ofmt_ctx);
    return shutDown(0);
} 

