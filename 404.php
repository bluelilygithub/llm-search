<?php
// Get the header template part (header.php).
get_header(); 

// Get the specific 404 page content by slug
$error_page = get_page_by_path('system-pages/page-not-found');

if ( $error_page ) :
    // Set up the post data for the 404 page
    $post = $error_page;
    setup_postdata( $post );
    
    // 1) Safely fetch the ACF banner field
    $featured_image = get_field( 'page_heading_banner' );
    if ( is_array( $featured_image ) && ! empty( $featured_image['id'] ) ) {
        $src = wp_get_attachment_image_src( $featured_image['id'], 'bluelily_banner_header' );
        $imageHeaderBkground = is_array( $src ) ? $src[0] : false;
    } else {
        // Fallback to default option banner
        $fallback = get_field( 'default_page_heading_image', 'option' );
        $imageHeaderBkground = isset( $fallback['url'] ) ? $fallback['url'] : false;
    }
    
    // Final fallback if still not set
    if ( ! $imageHeaderBkground ) {
        $imageHeaderBkground = get_template_directory_uri() . '/assets/img/fallback-banner.jpg';
    }
    
    // 2) Determine featured image or default page feature image
    if ( has_post_thumbnail() ) {
        $featured_image = bluelily_get_featured_image( get_the_ID(), 'full' );
    } else {
        $default_feature = get_field( 'default_page_feature_image', 'option' );
        $featured_image = isset( $default_feature['url'] ) ? $default_feature['url'] : '';
    }
    
    // 3) Pass variables to inner_header.php for rendering
    set_query_var( 'banner_url',       $imageHeaderBkground );
    set_query_var( 'featured_image',   $featured_image );
    include get_theme_file_path( 'inner_header.php' );
    
    // 4) Load the appropriate content template based on post type
    $post_type = $post->post_type;
    if ( locate_template( 'template-parts/content-' . $post_type . '.php' ) ) {
        get_template_part( 'template-parts/content', $post_type );
    }
    
    // Reset post data
    wp_reset_postdata();
    
else :
    // Fallback if the 404 page doesn't exist
    ?>
    <div class="container">
        <div class="row">
            <div class="col-12">
                <h1>Page Not Found</h1>
                <p>Sorry, the page you are looking for could not be found.</p>
                <a href="<?php echo home_url(); ?>" class="btn btn-primary">Return Home</a>
            </div>
        </div>
    </div>
    <?php
endif;

// Get the footer template part (footer.php).
get_footer();
?>